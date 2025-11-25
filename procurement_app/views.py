from django.db.models import Q
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
from documents.models import DocumentExtractionResult, ReceiptValidationResult
from documents.services import extraction as extraction_service, validation as validation_service
from procurement_app.models import PurchaseRequest
from procurement_app.permissions import IsOwnerOrReadOnly
from procurement_app.serializers import (
    ApprovalActionSerializer,
    DocumentExtractionResultSerializer,
    PurchaseRequestSerializer,
    ReceiptUploadSerializer,
    ReceiptValidationResultSerializer,
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
        .select_related("created_by", "purchase_order", "receipt_validation")
        .prefetch_related("items", "approvals", "extraction_results")
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
