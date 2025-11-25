from __future__ import annotations

import json
import logging
from typing import Any, Dict

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

_model = None

SYSTEM_PROMPT = """
You are an intelligent document parser for a procure-to-pay platform.
Given OCR text from financial documents (proforma, receipt, or purchase order),
produce structured JSON with the following schema:
{
  "vendor_name": "<string>",
  "currency": "<string>",
  "document_date": "<YYYY-MM-DD or empty string>",
  "total_amount": <number>,
  "items": [
     {
        "name": "<string>",
        "description": "<string>",
        "quantity": <number>,
        "unit_price": <number>,
        "total_price": <number>
     }
  ],
  "terms": "<string>"
}
Rules:
- If a field isn't present, leave it as an empty string or 0 (do not invent values).
- Items array can be empty if no line items are discoverable.
- Only return valid JSON. Do not include explanations.
"""


def _get_model():
    global _model
    if _model or not settings.GEMINI_API_KEY or not genai:
        return _model
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Unable to initialize Gemini model: %s", exc)
        _model = None
    return _model


def structure_document(raw_text: str, doc_type: str) -> Dict[str, Any]:
    model = _get_model()
    if not model:
        logger.warning("Gemini model unavailable; returning empty structure.")
        return {}
    if not raw_text:
        return {}
    prompt = (
        f"Document type: {doc_type or 'unknown'}.\n"
        "Extract the data using the schema described in the system prompt from the following text:\n"
        f"```{raw_text}```"
    )
    try:
        response = model.generate_content(prompt)
        content = ""
        if response and response.candidates:
            parts = response.candidates[0].content.parts
            if parts:
                content = parts[0].text or ""
        if not content and hasattr(response, "text"):
            content = response.text or ""
        if not content:
            logger.warning("Gemini returned empty content.")
            return {}
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("Gemini response was not valid JSON: %s", exc)
        return {}
    except Exception as exc:  # pragma: no cover
        logger.warning("Gemini extraction failed: %s", exc)
        return {}


def compare_documents(po_data: Dict[str, Any], receipt_data: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if not model:
        return {}
    prompt = (
        "You are comparing a purchase order against a receipt. "
        "Identify matches and mismatches across vendor, totals, and items. "
        "Respond in JSON with: {\"summary\": \"...\", \"issues\": [\"...\"], \"confidence\": 0-1}.\n"
        f"Purchase Order JSON:\n```{json.dumps(po_data, default=str)}```\n"
        f"Receipt JSON:\n```{json.dumps(receipt_data, default=str)}```"
    )
    try:
        response = model.generate_content(prompt)
        content = ""
        if response and response.candidates:
            parts = response.candidates[0].content.parts
            if parts:
                content = parts[0].text or ""
        if not content and hasattr(response, "text"):
            content = response.text or ""
        if not content:
            return {}
        return json.loads(content)
    except Exception as exc:  # pragma: no cover
        logger.warning("Gemini validation summary failed: %s", exc)
        return {}
