from django.contrib import admin

from documents.models import DocumentExtractionResult, ReceiptValidationResult


@admin.register(DocumentExtractionResult)
class DocumentExtractionResultAdmin(admin.ModelAdmin):
    list_display = ("purchase_request", "doc_type", "confidence_score", "engine_used", "created_at")
    search_fields = ("purchase_request__title", "doc_type")
    list_filter = ("doc_type", "engine_used")


@admin.register(ReceiptValidationResult)
class ReceiptValidationResultAdmin(admin.ModelAdmin):
    list_display = ("purchase_request", "is_match", "score", "created_at")
    search_fields = ("purchase_request__title",)
