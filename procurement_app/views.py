from datetime import timedelta
from django.db.models import Count, Q, Sum
from django.views.decorators.cache import cache_page
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsFinance
from core.security_logging import log_receipt_validation, log_request_approved
from core.throttling import HeavyActionThrottle
from django.utils import timezone
from django.utils.dateparse import parse_date
from documents.models import DocumentExtractionResult, ReceiptValidationResult
from documents.services import extraction as extraction_service, validation as validation_service
from procurement_app.models import (
    FinanceDecision,
    PurchaseRequest,
    RequestComment,
    RequestCommentReceipt,
    SavedRequestView,
)
from procurement_app.permissions import IsOwnerOrReadOnly
from procurement_app.serializers import (
    ApprovalActionSerializer,
    DocumentExtractionResultSerializer,
    FinanceDecisionSerializer,
    PurchaseRequestSerializer,
    RequestCommentSerializer,
    ReceiptUploadSerializer,
    ReceiptValidationResultSerializer,
    SavedRequestViewSerializer,
)
from procurement_app.services import workflow
from procurement_app.filters import PurchaseRequestFilter


@cache_page(60)
@api_view(["GET"])
@permission_classes([AllowAny])
def home(request):
    return Response(
        {
            "name": "Smart Procure-to-Pay API",
            "version": "0.1.0",
        }
    )


class PurchaseRequestViewSet(viewsets.ModelViewSet):
    """CRUD endpoints for purchase requests plus workflow actions."""

    serializer_class = PurchaseRequestSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    queryset = (
        PurchaseRequest.objects.all()
        .select_related("created_by", "purchase_order", "receipt_validation", "finance_decision")
        .prefetch_related("items", "approvals", "extraction_results", "comments", "comments__receipts")
    )
    filterset_class = PurchaseRequestFilter
    search_fields = ["title", "reference", "vendor_name", "created_by__full_name"]
    ordering_fields = ["created_at", "amount_estimated", "needed_by"]
    ordering = ["-created_at"]

    action_serializer_classes = {
        "approve": ApprovalActionSerializer,
        "reject": ApprovalActionSerializer,
        "submit_receipt": ReceiptUploadSerializer,
    }
    heavy_throttle_actions = {"create", "submit_receipt"}

    def get_throttles(self):
        throttles = super().get_throttles()
        if getattr(self, "action", None) in self.heavy_throttle_actions:
            throttles.append(HeavyActionThrottle())
        return throttles

    def get_permissions(self):
        if self.action in ("list", "retrieve", "create", "update", "partial_update"):
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if hasattr(self, "action") and self.action in self.action_serializer_classes:
            return self.action_serializer_classes[self.action]
        return super().get_serializer_class()

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if not user.is_authenticated:
            return qs.none()

        if user.role == "staff":
            return qs.filter(created_by=user)
        if user.role == "approver_lvl1":
            return qs.filter(
                Q(status=PurchaseRequest.Status.PENDING, current_approval_level=1)
                | Q(approvals__approver=user)
            ).distinct()
        if user.role == "approver_lvl2":
            return qs.filter(
                Q(status=PurchaseRequest.Status.PENDING, current_approval_level=2)
                | Q(approvals__approver=user)
            ).distinct()
        if user.role == "finance":
            return qs.filter(status__in=[PurchaseRequest.Status.APPROVED, PurchaseRequest.Status.REJECTED])
        return qs

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        start = self.request.query_params.get("start_date")
        end = self.request.query_params.get("end_date")
        if start:
            parsed = parse_date(start)
            if parsed:
                queryset = queryset.filter(created_at__date__gte=parsed)
        if end:
            parsed = parse_date(end)
            if parsed:
                queryset = queryset.filter(created_at__date__lte=parsed)
        return queryset

    def perform_create(self, serializer):
        if self.request.user.role != "staff":
            raise PermissionDenied("Only staff members can create purchase requests.")
        proforma_file = self.request.FILES.get("proforma_file")
        if not proforma_file:
            raise serializers.ValidationError({"proforma_file": "This field is required."})
        purchase_request = serializer.save()
        if hasattr(proforma_file, "seek"):
            proforma_file.seek(0)
        extraction_service.extract_document(
            purchase_request=purchase_request,
            doc_type=DocumentExtractionResult.DocTypes.PROFORMA,
            uploaded_file=proforma_file,
        )

    @action(detail=True, methods=["patch"], url_path="approve", serializer_class=ApprovalActionSerializer)
    def approve(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.user.role not in ("approver_lvl1", "approver_lvl2"):
            raise PermissionDenied("Only approvers can approve requests.")
        try:
            updated_request = workflow.approve_request(pk, request.user, serializer.validated_data.get("comment", ""))
        except workflow.WorkflowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_request_approved(request.user, updated_request)
        response_serializer = PurchaseRequestSerializer(updated_request, context=self.get_serializer_context())
        return Response(response_serializer.data)

    @action(detail=True, methods=["patch"], url_path="reject", serializer_class=ApprovalActionSerializer)
    def reject(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.user.role not in ("approver_lvl1", "approver_lvl2"):
            raise PermissionDenied("Only approvers can reject requests.")
        try:
            updated_request = workflow.reject_request(pk, request.user, serializer.validated_data.get("comment", ""))
        except workflow.WorkflowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        response_serializer = PurchaseRequestSerializer(updated_request, context=self.get_serializer_context())
        return Response(response_serializer.data)

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        purchase_request = self.get_object()
        if request.method == "GET":
            serializer = RequestCommentSerializer(purchase_request.comments.all(), many=True)
            if request.user.is_authenticated:
                unread = purchase_request.comments.exclude(receipts__user=request.user)
                for comment in unread:
                    RequestCommentReceipt.objects.get_or_create(comment=comment, user=request.user)
            return Response(serializer.data)
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        body = request.data.get("body", "").strip()
        if not body:
            raise serializers.ValidationError({"body": "Comment text is required."})
        comment = RequestComment.objects.create(
            purchase_request=purchase_request,
            author=request.user,
            body=body,
        )
        serializer = RequestCommentSerializer(comment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path="submit-receipt",
        parser_classes=[MultiPartParser, FormParser],
        serializer_class=ReceiptUploadSerializer,
    )
    def submit_receipt(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase_request = self.get_object()
        if purchase_request.created_by_id != request.user.id:
            raise PermissionDenied("Only the request owner can submit a receipt.")
        if purchase_request.status != PurchaseRequest.Status.APPROVED:
            raise PermissionDenied("Receipts can only be submitted for approved requests.")
        if not hasattr(purchase_request, "purchase_order"):
            raise PermissionDenied("Purchase order not available for this request.")

        receipt_file = serializer.validated_data["receipt"]
        extraction = extraction_service.extract_document(
            purchase_request=purchase_request,
            doc_type=DocumentExtractionResult.DocTypes.RECEIPT,
            uploaded_file=receipt_file,
            update_request=False,
        )
        receipt_data = extraction.final_data
        validation_payload = validation_service.validate_receipt_against_po(
            purchase_request.purchase_order.structured_data or {},
            receipt_data,
        )
        validation, _ = ReceiptValidationResult.objects.update_or_create(
            purchase_request=purchase_request,
            defaults=validation_payload,
        )
        log_receipt_validation(request.user, purchase_request, validation)
        response_serializer = PurchaseRequestSerializer(purchase_request, context=self.get_serializer_context())
        data = {
            "request": response_serializer.data,
            "extraction": DocumentExtractionResultSerializer(extraction).data,
            "validation": ReceiptValidationResultSerializer(validation).data,
        }
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="bulk-approve")
    def bulk_approve(self, request):
        if request.user.role not in ("approver_lvl1", "approver_lvl2"):
            raise PermissionDenied("Only approvers can approve requests.")
        request_ids = request.data.get("request_ids") or []
        comment = request.data.get("comment", "")
        if not isinstance(request_ids, list) or not request_ids:
            raise serializers.ValidationError({"request_ids": "Provide a list of request IDs."})
        approved = []
        errors = []
        for req_id in request_ids:
            try:
                updated = workflow.approve_request(req_id, request.user, comment)
                approved.append(str(updated.id))
            except workflow.WorkflowError as exc:
                errors.append({"id": str(req_id), "detail": str(exc)})
        return Response({"approved": approved, "errors": errors})

    @action(detail=True, methods=["get"], url_path="validation")
    def latest_validation(self, request, pk=None):
        purchase_request = self.get_object()
        result = getattr(purchase_request, "receipt_validation", None)
        if not result:
            return Response({"detail": "No validation available."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ReceiptValidationResultSerializer(result).data)

    @action(detail=True, methods=["get"], url_path=r"extraction/(?P<doc_type>[^/.]+)")
    def extraction(self, request, pk=None, doc_type=None):
        purchase_request = self.get_object()
        result = purchase_request.extraction_results.filter(doc_type=doc_type).first()
        if not result:
            return Response({"detail": "No extraction result available."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DocumentExtractionResultSerializer(result).data)


class FinanceRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Finance-specific list endpoints with dedicated permission."""

    serializer_class = PurchaseRequestSerializer
    permission_classes = [IsAuthenticated, IsFinance]
    queryset = PurchaseRequestViewSet.queryset
    filterset_class = PurchaseRequestFilter
    search_fields = ["title", "reference", "vendor_name", "created_by__full_name"]
    ordering_fields = ["created_at", "amount_estimated"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        else:
            qs = qs.filter(status=PurchaseRequest.Status.APPROVED)

        validation_filter = self.request.query_params.get("validation")
        if validation_filter == "matched":
            qs = qs.filter(receipt_validation__is_match=True)
        elif validation_filter == "mismatched":
            qs = qs.filter(receipt_validation__is_match=False)
        elif validation_filter == "pending":
            qs = qs.filter(receipt_validation__isnull=True)

        mismatches = self.request.query_params.get("mismatches")
        if mismatches == "true":
            qs = qs.filter(receipt_validation__is_match=False)
        return qs

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        start = self.request.query_params.get("start_date")
        end = self.request.query_params.get("end_date")
        if start:
            parsed = parse_date(start)
            if parsed:
                queryset = queryset.filter(created_at__date__gte=parsed)
        if end:
            parsed = parse_date(end)
            if parsed:
                queryset = queryset.filter(created_at__date__lte=parsed)
        return queryset

    @action(detail=False, methods=["get"], url_path="summary/vendor-spend")
    def vendor_spend(self, request):
        qs = self.filter_queryset(self.get_queryset())
        limit = int(request.query_params.get("limit", 5))
        spend = (
            qs.exclude(vendor_name="")
            .values("vendor_name")
            .annotate(total_amount=Sum("amount_estimated"), count_requests=Count("id"))
            .order_by("-total_amount")[:limit]
        )
        return Response(list(spend))

    @action(detail=False, methods=["get"], url_path="summary/cashout-forecast")
    def cashout_forecast(self, request):
        weeks = int(request.query_params.get("weeks", 8))
        now = timezone.now().date()
        buckets = []
        qs = self.filter_queryset(self.get_queryset())
        for idx in range(weeks):
            start = now + timedelta(weeks=idx)
            end = start + timedelta(days=6)
            bucket_total = qs.filter(needed_by__range=(start, end)).aggregate(total=Sum("amount_estimated"))["total"] or 0
            bucket_count = qs.filter(needed_by__range=(start, end)).count()
            buckets.append(
                {
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                    "amount_due": float(bucket_total),
                    "count_requests": bucket_count,
                }
            )
        return Response({"buckets": buckets})

    @action(detail=True, methods=["get"], url_path="validation-detail")
    def validation_detail(self, request, pk=None):
        purchase_request = self.get_object()
        serializer = PurchaseRequestSerializer(purchase_request, context=self.get_serializer_context())
        validation = ReceiptValidationResultSerializer(getattr(purchase_request, "receipt_validation", None)).data
        decision = FinanceDecisionSerializer(getattr(purchase_request, "finance_decision", None)).data
        return Response({"request": serializer.data, "validation": validation, "decision": decision})

    @action(detail=True, methods=["post"], url_path="validation-decision")
    def validation_decision(self, request, pk=None):
        if request.user.role != "finance":
            raise PermissionDenied("Only finance team members can record decisions.")
        purchase_request = self.get_object()
        decision_value = request.data.get("decision")
        note = request.data.get("note", "")
        if decision_value not in FinanceDecision.Decision.values:
            raise serializers.ValidationError({"decision": "Invalid decision."})
        decision, _ = FinanceDecision.objects.update_or_create(
            purchase_request=purchase_request,
            defaults={"decision": decision_value, "note": note, "decided_by": request.user},
        )
        serializer = FinanceDecisionSerializer(decision)
        return Response(serializer.data)


class SavedRequestViewSet(viewsets.ModelViewSet):
    serializer_class = SavedRequestViewSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        return SavedRequestView.objects.filter(user=self.request.user).order_by("name")

    def perform_create(self, serializer):
        if SavedRequestView.objects.filter(user=self.request.user).count() >= 10:
            raise serializers.ValidationError({"detail": "Maximum of 10 saved views reached."})
        serializer.save(user=self.request.user)
