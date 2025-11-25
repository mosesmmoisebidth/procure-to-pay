from __future__ import annotations

import re
from decimal import Decimal
from typing import Dict, List

CURRENCY_REGEX = re.compile(r"\b(USD|EUR|GBP|UGX|KES|TZS|RWF)\b", re.IGNORECASE)
AMOUNT_REGEX = re.compile(r"([A-Z]{3})?\s?\$?([\d,]+\.\d{2})")
VENDOR_REGEX = re.compile(r"vendor\s*[:\-]\s*(.*)", re.IGNORECASE)
ITEM_LINE_REGEX = re.compile(r"(?P<name>[\w\s]+?)\s+(?P<qty>\d+)\s+x\s+(?P<price>[\d,.]+)", re.IGNORECASE)


def _clean_amount(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", ""))
    except Exception:
        return None


def parse_fields_from_raw_text(raw_text: str, doc_type: str) -> Dict:
    """
    Very lightweight heuristic parser for vendor, currency, totals, and line items.
    """

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    vendor = None
    currency = None
    total_amount = None
    items: List[Dict] = []

    for line in lines[:10]:
        vendor_match = VENDOR_REGEX.search(line)
        if vendor_match:
            vendor = vendor_match.group(1).strip()
            break

    if not vendor and lines:
        vendor = lines[0]

    currency_match = CURRENCY_REGEX.search(raw_text)
    if currency_match:
        currency = currency_match.group(1).upper()

    for match in AMOUNT_REGEX.finditer(raw_text):
        curr = match.group(1)
        amt = _clean_amount(match.group(2))
        if curr and not currency:
            currency = curr.upper()
        if amt:
            total_amount = amt

    for line in lines:
        match = ITEM_LINE_REGEX.search(line)
        if match:
            qty = int(match.group("qty"))
            unit_price = _clean_amount(match.group("price")) or Decimal("0")
            items.append(
                {
                    "name": match.group("name").strip(),
                    "description": "",
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total_price": unit_price * qty,
                }
            )

    return {
        "vendor_name": vendor,
        "currency": currency,
        "total_amount": total_amount,
        "items": items,
    }
