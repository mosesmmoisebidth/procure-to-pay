from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from rest_framework import serializers

from accounts.serializers import UserSerializer
from documents.models import DocumentExtractionResult, ReceiptValidationResult
from procurement_app.models import Approval, PurchaseOrder, PurchaseRequest, RequestItem
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


class PurchaseRequestSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    items = RequestItemSerializer(many=True, read_only=True)
    approvals = ApprovalSerializer(many=True, read_only=True)
    purchase_order = PurchaseOrderSerializer(read_only=True)
    latest_validation = serializers.SerializerMethodField()
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
            "created_at",
            "updated_at",
        )

    def get_latest_validation(self, obj: PurchaseRequest):
        result = getattr(obj, "receipt_validation", None)
        return ReceiptValidationResultSerializer(result).data if result else None

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
