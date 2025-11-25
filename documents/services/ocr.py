from __future__ import annotations

import logging
import tempfile
from pathlib import Path

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

logger = logging.getLogger(__name__)

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None
    logger.warning("pytesseract is not installed; OCR for images will be limited.")


def _as_temp_file(file_obj) -> Path:
    if isinstance(file_obj, (str, Path)):
        return Path(file_obj)
    suffix = ""
    if hasattr(file_obj, "name") and isinstance(file_obj.name, str):
        suffix = Path(file_obj.name).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix or None)
    tmp.write(file_obj.read())
    tmp.flush()
    tmp.close()
    file_obj.seek(0)
    return Path(tmp.name)


def extract_text_and_tokens(file_obj) -> tuple[str, list[dict]]:
    """
    Extract raw text and positional tokens from PDFs/images.
    """

    if not pdfplumber and not pytesseract:
        raise RuntimeError("pdfplumber or pytesseract is required for OCR operations.")

    path = _as_temp_file(file_obj)
    tokens: list[dict] = []
    text_chunks: list[str] = []

    try:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            if not pdfplumber:
                raise RuntimeError("pdfplumber is required for PDF extraction.")
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text_chunks.append(page.extract_text() or "")
                    for word in page.extract_words():
                        tokens.append(
                            {
                                "text": word.get("text", ""),
                                "bbox": [
                                    word.get("x0", 0),
                                    word.get("top", 0),
                                    word.get("x1", 0),
                                    word.get("bottom", 0),
                                ],
                                "page": page.page_number,
                            }
                        )
        else:
            if not pytesseract or not Image:
                raise RuntimeError("pytesseract and Pillow are required for non-PDF OCR")
            try:
                image = Image.open(path)
            except Exception as exc:  # pragma: no cover - fallback to informative error
                raise RuntimeError(f"Unable to open document as image for OCR: {exc}") from exc
            text_chunks.append(pytesseract.image_to_string(image))
            ocr_data = pytesseract.image_to_data(image, output_type="dict")
            for i in range(len(ocr_data["text"])):
                tokens.append(
                    {
                        "text": ocr_data["text"][i],
                        "bbox": [
                            ocr_data["left"][i],
                            ocr_data["top"][i],
                            ocr_data["left"][i] + ocr_data["width"][i],
                            ocr_data["top"][i] + ocr_data["height"][i],
                        ],
                        "page": 1,
                    }
                )
    finally:
        if path.exists() and path.name.startswith("tmp"):
            path.unlink()

    return "\n".join(text_chunks).strip(), tokens
