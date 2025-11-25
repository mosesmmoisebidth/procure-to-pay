from __future__ import annotations

import logging
from typing import Dict, List

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification  # type: ignore
except ImportError:  # pragma: no cover
    LayoutLMv3Processor = None
    LayoutLMv3ForTokenClassification = None

_layoutlm_model = None
_layoutlm_processor = None


def _load_model():
    global _layoutlm_model, _layoutlm_processor
    if _layoutlm_model or not settings.DOC_AI_ENABLED:
        return _layoutlm_model, _layoutlm_processor
    if not LayoutLMv3ForTokenClassification or not LayoutLMv3Processor:
        logger.warning("DOC_AI_ENABLED but transformers not installed; skipping LayoutLMv3.")
        return None, None
    _layoutlm_processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base")
    _layoutlm_model = LayoutLMv3ForTokenClassification.from_pretrained("microsoft/layoutlmv3-base")
    return _layoutlm_model, _layoutlm_processor


def extract_fields_with_layoutlmv3(tokens: List[dict], doc_type: str) -> Dict:
    """
    Placeholder LayoutLMv3 integration. In production, feed OCR tokens and bounding boxes into the processor/model.
    """

    model, processor = _load_model()
    if not (model and processor):
        return {}

    # TODO: implement actual LayoutLM inference. Returning empty dict keeps pipeline intact.
    logger.info("LayoutLMv3 model loaded but inference is not implemented in this environment.")
    return {}
