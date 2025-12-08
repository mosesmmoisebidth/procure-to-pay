from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from rest_framework import serializers

from accounts.serializers import UserSerializer
from documents.models import DocumentExtractionResult, ReceiptValidationResult
from procurement_app.models import (
    Approval,
    FinanceDecision,
    PurchaseOrder,
    PurchaseRequest,
    RequestComment,
    RequestCommentReceipt,
    RequestItem,
    SavedRequestView,
)
from procurement_app.validators import validate_document


class RequestItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestItem
        fields = (
            "id",
            "name",
            "description",
            "quantity",
            "unit_price",
            "total_price",
        )
        read_only_fields = fields
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
        }


class ApprovalSerializer(serializers.ModelSerializer):
    approver = UserSerializer(read_only=True)

    class Meta:
        model = Approval
        fields = (
            "id",
            "approver",
            "level",
            "decision",
            "comment",
            "created_at",
        )
        read_only_fields = fields


class PurchaseOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrder
        fields = (
            "po_number",
            "vendor_name",
            "currency",
            "issue_date",
            "total_amount",
            "terms",
            "firebase_url",
            "structured_data",
        )
        read_only_fields = fields


class DocumentExtractionResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentExtractionResult
        fields = (
            "id",
            "doc_type",
            "firebase_url",
            "raw_text",
            "baseline_data",
            "model_data",
            "final_data",
            "confidence_score",
            "created_at",
        )
        read_only_fields = fields


class ReceiptValidationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptValidationResult
        fields = (
            "id",
            "is_match",
            "score",
            "details",
            "created_at",
        )
        read_only_fields = fields


class RequestCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = RequestComment
        fields = ("id", "body", "author", "created_at")
        read_only_fields = ("id", "author", "created_at")


class SavedRequestViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedRequestView
        fields = ("id", "name", "filters", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class FinanceDecisionSerializer(serializers.ModelSerializer):
    decided_by = UserSerializer(read_only=True)

    class Meta:
        model = FinanceDecision
        fields = ("id", "decision", "note", "decided_by", "created_at", "updated_at")
        read_only_fields = ("id", "decided_by", "created_at", "updated_at")


PIPELINE_STAGES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("level1", "Level 1 Approval"),
    ("level2", "Level 2 Approval"),
    ("po", "PO Issued"),
    ("receipt", "Receipt Uploaded"),
    ("validated", "Validated"),
    ("paid", "Paid"),
]


def calculate_risk(request_obj: PurchaseRequest):
    reasons = []
    amount = request_obj.amount_estimated or Decimal("0")
    if amount >= Decimal("50000"):
        reasons.append("Amount > 50,000")
    elif amount >= Decimal("25000"):
        reasons.append("Amount > 25,000")
    if not request_obj.vendor_name:
        reasons.append("Missing vendor")
    if request_obj.status == PurchaseRequest.Status.PENDING and request_obj.current_approval_level == 2:
        reasons.append("Awaiting Level 2 approval")
    level = PurchaseRequest.RiskLevel.LOW
    if len(reasons) >= 2:
        level = PurchaseRequest.RiskLevel.HIGH
    elif reasons:
        level = PurchaseRequest.RiskLevel.MEDIUM
    return level, reasons


class PurchaseRequestSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    items = RequestItemSerializer(many=True, read_only=True)
    approvals = ApprovalSerializer(many=True, read_only=True)
    purchase_order = PurchaseOrderSerializer(read_only=True)
    latest_validation = serializers.SerializerMethodField()
    stage_history = serializers.SerializerMethodField()
    current_stage = serializers.SerializerMethodField()
    next_action = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    has_unread_comments = serializers.SerializerMethodField()
    risk_summary = serializers.SerializerMethodField()
    proforma_file = serializers.FileField(
        write_only=True,
        required=False,
        help_text="Supporting document uploaded via multipart/form-data. Required on creation.",
        allow_null=True,
        validators=[validate_document],
    )

    class Meta:
        model = PurchaseRequest
        fields = (
            "id",
            "reference",
            "title",
            "description",
            "category",
            "amount_estimated",
            "amount_from_proforma",
            "currency",
            "vendor_name",
            "status",
            "current_approval_level",
            "required_approval_levels",
            "risk_level",
            "risk_reasons",
            "created_by",
            "needed_by",
            "notes",
            "proforma_url",
            "purchase_order_url",
            "receipt_url",
            "proforma_file",
            "items",
            "approvals",
            "purchase_order",
            "latest_validation",
            "stage_history",
            "current_stage",
            "next_action",
            "comment_count",
            "has_unread_comments",
            "risk_summary",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "reference",
            "vendor_name",
            "currency",
            "amount_from_proforma",
            "status",
            "current_approval_level",
            "created_by",
            "proforma_url",
            "purchase_order_url",
            "receipt_url",
            "purchase_order",
            "latest_validation",
            "stage_history",
            "current_stage",
            "next_action",
            "comment_count",
            "has_unread_comments",
            "risk_summary",
            "created_at",
            "updated_at",
        )

    def get_latest_validation(self, obj: PurchaseRequest):
        result = getattr(obj, "receipt_validation", None)
        return ReceiptValidationResultSerializer(result).data if result else None

    def _timeline_event(self, stage_key, label, completed_at=None, actor=None, comment=None):
        return {
            "stage": stage_key,
            "label": label,
            "completed_at": completed_at,
            "actor": actor,
            "comment": comment,
        }

    def get_stage_history(self, obj: PurchaseRequest):
        history = []
        history.append(
            self._timeline_event(
                "draft",
                "Draft",
                completed_at=obj.created_at,
                actor=getattr(obj.created_by, "full_name", None) or obj.created_by.username,
            )
        )
        history.append(
            self._timeline_event(
                "submitted",
                "Submitted",
                completed_at=obj.created_at,
                actor=getattr(obj.created_by, "full_name", None) or obj.created_by.username,
            )
        )
        approvals = list(obj.approvals.all())
        level1 = next((apr for apr in approvals if apr.level == 1 and apr.decision == Approval.Decision.APPROVED), None)
        if level1:
            history.append(
                self._timeline_event(
                    "level1",
                    "Level 1 Approval",
                    completed_at=level1.created_at,
                    actor=getattr(level1.approver, "full_name", None) or level1.approver.username,
                    comment=level1.comment,
                )
            )
        else:
            history.append(self._timeline_event("level1", "Level 1 Approval"))
        level2 = next((apr for apr in approvals if apr.level == 2 and apr.decision == Approval.Decision.APPROVED), None)
        if level2:
            history.append(
                self._timeline_event(
                    "level2",
                    "Level 2 Approval",
                    completed_at=level2.created_at,
                    actor=getattr(level2.approver, "full_name", None) or level2.approver.username,
                    comment=level2.comment,
                )
            )
        else:
            history.append(self._timeline_event("level2", "Level 2 Approval"))
        po = getattr(obj, "purchase_order", None)
        if po:
            history.append(
                self._timeline_event(
                    "po",
                    "PO Issued",
                    completed_at=po.created_at,
                    actor=getattr(obj.created_by, "full_name", None),
                )
            )
        else:
            history.append(self._timeline_event("po", "PO Issued"))
        extraction_qs = getattr(obj, "extraction_results", None)
        extraction_iterable = extraction_qs.all() if extraction_qs is not None else DocumentExtractionResult.objects.filter(purchase_request=obj)
        receipt_event = next(
            (res for res in extraction_iterable if res.doc_type == DocumentExtractionResult.DocTypes.RECEIPT),
            None,
        )
        if receipt_event:
            history.append(
                self._timeline_event(
                    "receipt",
                    "Receipt Uploaded",
                    completed_at=receipt_event.created_at,
                    actor=getattr(obj.created_by, "full_name", None),
                )
            )
        else:
            history.append(self._timeline_event("receipt", "Receipt Uploaded"))
        validation = getattr(obj, "receipt_validation", None)
        if validation:
            history.append(
                self._timeline_event(
                    "validated",
                    "Validated",
                    completed_at=validation.created_at,
                    actor=None,
                )
            )
        else:
            history.append(self._timeline_event("validated", "Validated"))
        decision = getattr(obj, "finance_decision", None)
        if decision:
            history.append(
                self._timeline_event(
                    "paid",
                    "Finance Decision",
                    completed_at=decision.created_at,
                    actor=getattr(decision.decided_by, "full_name", None),
                    comment=decision.note,
                )
            )
        else:
            history.append(self._timeline_event("paid", "Finance Decision"))
        return history

    def get_current_stage(self, obj: PurchaseRequest):
        history = self.get_stage_history(obj)
        completed = [event for event in history if event["completed_at"]]
        return completed[-1]["stage"] if completed else history[0]["stage"]

    def get_next_action(self, obj: PurchaseRequest):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        base = {"type": "none", "label": "No action required", "deadline": None}
        if obj.status == PurchaseRequest.Status.REJECTED:
            base.update({"type": "edit_request", "label": "Edit and resubmit"})
            return base
        if obj.status == PurchaseRequest.Status.PENDING:
            if user and user == obj.created_by:
                base.update({"type": "wait_for_approval", "label": "Waiting on approvers"})
            else:
                base.update({"type": "review_request", "label": "Review request"})
            return base
        if obj.status == PurchaseRequest.Status.APPROVED:
            if not obj.receipt_url:
                base.update(
                    {
                        "type": "upload_receipt",
                        "label": "Upload receipt",
                        "deadline": obj.needed_by.isoformat() if obj.needed_by else None,
                    }
                )
                return base
            validation = getattr(obj, "receipt_validation", None)
            if not validation:
                base.update({"type": "wait_for_validation", "label": "Awaiting validation"})
                return base
        return base

    def get_comment_count(self, obj: PurchaseRequest):
        return obj.comments.count()

    def get_has_unread_comments(self, obj: PurchaseRequest):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.comments.exclude(receipts__user=request.user).exists()

    def get_risk_summary(self, obj: PurchaseRequest):
        level, reasons = calculate_risk(obj)
        if obj.risk_level != level or obj.risk_reasons != reasons:
            obj.risk_level = level
            obj.risk_reasons = reasons
        return {"level": level, "reasons": reasons}

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        request = self.context.get("request")
        instance: PurchaseRequest | None = getattr(self, "instance", None)
        if instance and instance.status != PurchaseRequest.Status.PENDING:
            raise serializers.ValidationError("Only pending requests can be modified.")
        if request and request.method in ("POST", "PUT"):
            amount = attrs.get("amount_estimated")
            if amount is not None and Decimal(str(amount)) <= 0:
                raise serializers.ValidationError("Amount must be greater than zero.")
        return attrs

    def _should_skip(self, value) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and value.strip().lower() in {"", "string", "null"}:
            return True
        return False

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> PurchaseRequest:
        validated_data.pop("proforma_file", None)
        user = self.context["request"].user
        title = validated_data.get("title")
        amount = validated_data.get("amount_estimated")
        duplicate = PurchaseRequest.objects.filter(
            created_by=user,
            title=title,
            amount_estimated=amount,
            status=PurchaseRequest.Status.PENDING,
        ).exists()
        if duplicate:
            raise serializers.ValidationError(
                {"title": "A pending request with the same title and amount already exists."}
            )

        purchase_request = PurchaseRequest.objects.create(created_by=user, **validated_data)
        return purchase_request

    @transaction.atomic
    def update(self, instance: PurchaseRequest, validated_data: dict[str, Any]) -> PurchaseRequest:
        validated_data.pop("proforma_file", None)
        for attr, value in list(validated_data.items()):
            if self._should_skip(value):
                continue
            setattr(instance, attr, value)
        instance.save()
        return instance


class ReceiptUploadSerializer(serializers.Serializer):
    receipt = serializers.FileField(
        help_text="Required receipt/bill file uploaded after purchase.",
        allow_empty_file=False,
        validators=[validate_document],
    )


class ApprovalActionSerializer(serializers.Serializer):
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional comment that will appear in the approval history.",
    )
    needed_by = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
