import uuid

from django.db import models


class DocumentExtractionResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class DocTypes(models.TextChoices):
        PROFORMA = "proforma", "Proforma"
        PO = "po", "Purchase Order"
        RECEIPT = "receipt", "Receipt"

    purchase_request = models.ForeignKey(
        'procurement_app.PurchaseRequest',
        on_delete=models.CASCADE,
        related_name='extraction_results',
    )
    doc_type = models.CharField(max_length=20, choices=DocTypes.choices)
    firebase_url = models.URLField()
    raw_text = models.TextField(blank=True)
    baseline_data = models.JSONField(default=dict, blank=True)
    model_data = models.JSONField(null=True, blank=True)
    final_data = models.JSONField(default=dict)
    engine_used = models.CharField(max_length=64, default="baseline")
    confidence_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"{self.purchase_request_id} - {self.doc_type} ({self.confidence_score:.2f})"


class ReceiptValidationResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_request = models.OneToOneField(
        'procurement_app.PurchaseRequest',
        on_delete=models.CASCADE,
        related_name='receipt_validation',
    )
    is_match = models.BooleanField(default=False)
    score = models.FloatField(default=0.0)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Validation for request {self.purchase_request_id} ({self.score})"
