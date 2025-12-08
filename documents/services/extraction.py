from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from documents.models import DocumentExtractionResult
from documents.services import llm, ocr, storage
from procurement_app.models import PurchaseRequest, RequestItem

logger = logging.getLogger(__name__)


def _normalize_json(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    if isinstance(value, dict):
        return {k: _normalize_json(v) for k, v in value.items()}
    return value


####366.66667
@transaction.atomic
def extract_document(*, purchase_request: PurchaseRequest, doc_type: str, uploaded_file, update_request: bool = True) -> dict:
    firebase_url = storage.upload_file(uploaded_file, f"documents/{doc_type}")
    raw_text, _ = ocr.extract_text_and_tokens(uploaded_file)
    raw_text = (raw_text or "").replace("\x00", "")
    structured = llm.structure_document(raw_text, doc_type)
    if not structured:
        logger.warning("Gemini returned empty payload for doc_type=%s. Falling back to blank structure.", doc_type)
        structured = {
            "vendor_name": "",
            "currency": "",
            "document_date": "",
            "total_amount": 0,
            "items": [],
            "terms": "",
        }

    final_data = _normalize_json(structured)
    engine_label = "gemini" if structured else "ocr_only"
    confidence = 0.9 if structured else 0.4

    extraction = DocumentExtractionResult.objects.create(
        purchase_request=purchase_request,
        doc_type=doc_type,
        firebase_url=firebase_url,
        raw_text=raw_text,
        baseline_data=final_data,
        model_data=None,
        final_data=final_data,
        engine_used=engine_label,
        confidence_score=confidence,
    )

    if doc_type == DocumentExtractionResult.DocTypes.PROFORMA:
        purchase_request.proforma_url = firebase_url
        purchase_request.save(update_fields=["proforma_url", "updated_at"])
    if update_request and doc_type == DocumentExtractionResult.DocTypes.PROFORMA:
        _apply_proforma_data(purchase_request, final_data)

    if doc_type == DocumentExtractionResult.DocTypes.RECEIPT:
        purchase_request.receipt_url = firebase_url
        purchase_request.save(update_fields=["receipt_url", "updated_at"])

    return extraction


def _apply_proforma_data(purchase_request: PurchaseRequest, data: dict):
    vendor = data.get("vendor_name")
    currency = data.get("currency")
    total_amount = data.get("total_amount")
    items = data.get("items") or []

    update_fields = []
    if vendor:
        purchase_request.vendor_name = vendor
        update_fields.append("vendor_name")
    if currency:
        purchase_request.currency = currency
        update_fields.append("currency")
    if total_amount:
        try:
            purchase_request.amount_from_proforma = Decimal(str(total_amount))
            update_fields.append("amount_from_proforma")
        except Exception:
            logger.warning("Unable to coerce amount_from_proforma %s", total_amount)
    if update_fields:
        update_fields.append("updated_at")
        purchase_request.save(update_fields=update_fields)

    if items:
        purchase_request.items.all().delete()
        for item in items:
            RequestItem.objects.create(
                purchase_request=purchase_request,
                name=item.get("name") or "Item",
                description=item.get("description", ""),
                quantity=item.get("quantity") or 1,
                unit_price=item.get("unit_price") or Decimal("0"),
                total_price=item.get("total_price") or Decimal("0"),
            )
