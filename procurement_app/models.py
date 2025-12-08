import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def proforma_upload_to(instance, filename):  # pragma: no cover - legacy migration support
    return f"legacy/proforma/{filename}"


def purchase_order_upload_to(instance, filename):  # pragma: no cover
    return f"legacy/purchase_orders/{filename}"


def receipt_upload_to(instance, filename):  # pragma: no cover
    return f"legacy/receipts/{filename}"


def extraction_upload_to(instance, filename):  # pragma: no cover
    return f"legacy/extractions/{filename}"

class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def generate_reference() -> str:
    stamp = timezone.now().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:5].upper()
    return f"REQ-{stamp}-{suffix}"


class PurchaseRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    reference = models.CharField(max_length=32, unique=True, editable=False, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount_estimated = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
    )
    amount_from_proforma = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=10, blank=True)
    vendor_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=128, blank=True)
    needed_by = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="purchase_requests",
    )
    current_approval_level = models.PositiveSmallIntegerField(default=1)
    required_approval_levels = models.PositiveSmallIntegerField(default=2)
    proforma_url = models.URLField(blank=True)
    purchase_order_url = models.URLField(blank=True)
    receipt_url = models.URLField(blank=True)
    risk_level = models.CharField(max_length=8, choices=RiskLevel.choices, default=RiskLevel.LOW)
    risk_reasons = models.JSONField(default=list, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_reference()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.reference} — {self.title} ({self.get_status_display()})"


class RequestItem(UUIDModel):
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.quantity} x {self.unit_price})"


class Approval(TimeStampedModel):
    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="approvals",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approvals",
    )
    level = models.PositiveSmallIntegerField()
    decision = models.CharField(max_length=16, choices=Decision.choices)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.purchase_request_id} - L{self.level} {self.decision}"


class PurchaseOrder(TimeStampedModel):
    purchase_request = models.OneToOneField(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="purchase_order",
    )
    po_number = models.CharField(max_length=64, unique=True)
    vendor_name = models.CharField(max_length=255)
    currency = models.CharField(max_length=10, default="USD")
    issue_date = models.DateField()
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    terms = models.TextField(blank=True)
    firebase_url = models.URLField(blank=True)
    structured_data = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"PO {self.po_number}"


class SavedRequestView(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_request_views")
    name = models.CharField(max_length=100)
    filters = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("user", "name")
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.user} - {self.name}"


class RequestComment(TimeStampedModel):
    purchase_request = models.ForeignKey(
        PurchaseRequest, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="request_comments"
    )
    body = models.TextField()

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"Comment by {self.author} on {self.purchase_request_id}"


class RequestCommentReceipt(models.Model):
    comment = models.ForeignKey(RequestComment, on_delete=models.CASCADE, related_name="receipts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_receipts")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("comment", "user")


class FinanceDecision(TimeStampedModel):
    class Decision(models.TextChoices):
        MATCHED = "matched", "Matched"
        ACCEPTED_WITH_NOTE = "accepted_with_note", "Accepted with note"
        FLAGGED = "flagged", "Flagged"

    purchase_request = models.OneToOneField(
        PurchaseRequest, on_delete=models.CASCADE, related_name="finance_decision"
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="finance_decisions"
    )
    decision = models.CharField(max_length=32, choices=Decision.choices)
    note = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.purchase_request_id} - {self.decision}"
