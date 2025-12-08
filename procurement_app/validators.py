from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_UPLOAD_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")


def validate_document(file):
    if file.size > settings.MAX_UPLOAD_SIZE:
        raise ValidationError("File too large. Maximum size is 10 MB.")
    name = (file.name or "").lower()
    if not any(name.endswith(ext) for ext in ALLOWED_UPLOAD_EXTENSIONS):
        raise ValidationError("Unsupported file type. Only PDF or image files are allowed.")
