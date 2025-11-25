import uuid
from datetime import date
from io import BytesIO

from django.db import transaction
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from documents.models import DocumentExtractionResult
from documents.services import storage as storage_service
from procurement_app.models import PurchaseOrder, PurchaseRequest


def build_po_number() -> str:
    stamp = timezone.now().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"PO-{stamp}-{suffix}"


def _po_structured_data(request_obj: PurchaseRequest) -> dict:
    extraction = (
        request_obj.extraction_results.filter(doc_type=DocumentExtractionResult.DocTypes.PROFORMA).first()
    )
    base_items = extraction.final_data.get("items") if extraction else []
    vendor = request_obj.vendor_name or (extraction.final_data.get("vendor_name") if extraction else "")
    currency = request_obj.currency or (extraction.final_data.get("currency") if extraction else "USD")
    total_amount = float(request_obj.amount_from_proforma or request_obj.amount_estimated)
    if not base_items:
        base_items = [
            {
                "name": request_obj.title,
                "description": request_obj.description,
                "quantity": 1,
                "unit_price": float(request_obj.amount_estimated),
                "total_price": float(request_obj.amount_estimated),
            }
        ]
    return {
        "vendor_name": vendor,
        "currency": currency,
        "total_amount": total_amount,
        "items": base_items,
        "terms": "Payment within 30 days",
    }


def _build_po_pdf_bytes(po_number: str, request_obj: PurchaseRequest, structured_data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=40,
        leftMargin=40,
        topMargin=60,
        bottomMargin=40,
        title=f"Purchase Order {po_number}",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Purchase Order #{po_number}", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Vendor: {structured_data.get('vendor_name') or 'N/A'}", styles["Normal"]),
        Paragraph(f"Currency: {structured_data.get('currency') or 'USD'}", styles["Normal"]),
        Paragraph(
            f"Requested By: {request_obj.created_by.full_name or request_obj.created_by.username}",
            styles["Normal"],
        ),
        Paragraph(f"Issue Date: {date.today().isoformat()}", styles["Normal"]),
        Spacer(1, 18),
    ]

    table_data = [["Item", "Qty", "Unit Price", "Total"]]
    for item in structured_data.get("items", []):
        table_data.append(
            [
                item.get("name", ""),
                item.get("quantity", 0),
                f"{structured_data.get('currency', 'USD')} {item.get('unit_price', 0):,.2f}",
                f"{structured_data.get('currency', 'USD')} {item.get('total_price', 0):,.2f}",
            ]
        )
    table = Table(table_data, colWidths=[3 * inch, 0.8 * inch, 1.3 * inch, 1.3 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            f"<b>Total:</b> {structured_data.get('currency', 'USD')} "
            f"{structured_data.get('total_amount', 0):,.2f}",
            styles["Heading3"],
        )
    )
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(f"<b>Terms:</b><br/>{structured_data.get('terms') or 'Payment within 30 days.'}", styles["BodyText"])
    )
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


@transaction.atomic
def ensure_purchase_order_exists(request_obj: PurchaseRequest) -> PurchaseOrder:
    if hasattr(request_obj, "purchase_order"):
        return request_obj.purchase_order

    structured = _po_structured_data(request_obj)
    po_number = build_po_number()
    pdf_bytes = _build_po_pdf_bytes(po_number, request_obj, structured)
    firebase_url = storage_service.upload_bytes(pdf_bytes, "purchase_orders", f"{po_number}.pdf")

    po = PurchaseOrder.objects.create(
        purchase_request=request_obj,
        po_number=po_number,
        vendor_name=structured.get("vendor_name") or "",
        currency=structured.get("currency") or "USD",
        issue_date=date.today(),
        total_amount=structured.get("total_amount") or request_obj.amount_estimated,
        terms=structured.get("terms", ""),
        firebase_url=firebase_url,
        structured_data=structured,
    )

    request_obj.purchase_order_url = firebase_url
    request_obj.save(update_fields=["purchase_order_url", "updated_at"])

    DocumentExtractionResult.objects.create(
        purchase_request=request_obj,
        doc_type=DocumentExtractionResult.DocTypes.PO,
        firebase_url=firebase_url,
        raw_text="Generated internally",
        baseline_data=structured,
        model_data=None,
        final_data=structured,
        engine_used="generator",
        confidence_score=1.0,
    )
    return po
