from __future__ import annotations

import difflib
from decimal import Decimal
from typing import Dict, List

from documents.services import llm


def _normalize_name(name: str | None) -> str:
    return (name or "").strip().lower()


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def validate_receipt_against_po(po_data: Dict, receipt_data: Dict) -> Dict:
    details: Dict[str, Dict | List] = {}
    po_vendor = _normalize_name(po_data.get("vendor_name"))
    receipt_vendor = _normalize_name(receipt_data.get("vendor_name"))
    vendor_similarity = _similarity(po_vendor, receipt_vendor) if po_vendor or receipt_vendor else 0
    details["vendor_match"] = {
        "expected": po_data.get("vendor_name"),
        "found": receipt_data.get("vendor_name"),
        "similarity": round(vendor_similarity, 2),
    }

    po_total = Decimal(str(po_data.get("total_amount") or 0))
    receipt_total = Decimal(str(receipt_data.get("total_amount") or 0))
    difference = abs(po_total - receipt_total)
    details["total_amount_match"] = {
        "expected": float(po_total),
        "found": float(receipt_total),
        "difference": float(difference),
    }

    po_items = { _normalize_name(item.get("name")): item for item in po_data.get("items", []) }
    receipt_items = { _normalize_name(item.get("name")): item for item in receipt_data.get("items", []) }
    item_differences: List[Dict] = []

    for key, po_item in po_items.items():
        receipt_item = receipt_items.get(key)
        if not receipt_item:
            item_differences.append(
                {"item_name": po_item.get("name"), "issue": "missing_in_receipt"}
            )
            continue
        if po_item.get("quantity") != receipt_item.get("quantity"):
            item_differences.append(
                {
                    "item_name": po_item.get("name"),
                    "issue": "quantity mismatch",
                    "expected_quantity": po_item.get("quantity"),
                    "found_quantity": receipt_item.get("quantity"),
                }
            )
        if str(po_item.get("unit_price")) != str(receipt_item.get("unit_price")):
            item_differences.append(
                {
                    "item_name": po_item.get("name"),
                    "issue": "unit price mismatch",
                    "expected_unit_price": po_item.get("unit_price"),
                    "found_unit_price": receipt_item.get("unit_price"),
                }
            )
    details["item_differences"] = item_differences

    checks = [
        vendor_similarity >= 0.9,
        difference <= Decimal("0.05") * (po_total or Decimal("1")),
        len(item_differences) == 0,
    ]
    score = sum(1 for ok in checks if ok) / len(checks)
    llm_summary = llm.compare_documents(po_data, receipt_data)
    if llm_summary:
        details["llm_analysis"] = llm_summary
    return {"is_match": score >= 0.8, "score": round(score, 2), "details": details}
