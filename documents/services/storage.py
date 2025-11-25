from __future__ import annotations

import io
import mimetypes
import uuid

from django.conf import settings

try:
    import firebase_admin
    from firebase_admin import credentials, storage
except ImportError:  # pragma: no cover
    firebase_admin = None
    credentials = None
    storage = None

_firebase_app = None


def _initialize_app():
    global _firebase_app
    if _firebase_app:
        return _firebase_app
    if not firebase_admin:
        raise RuntimeError("firebase_admin is not installed. Please install firebase-admin to use storage services.")
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_FILE)
        _firebase_app = firebase_admin.initialize_app(
            cred,
            {"storageBucket": settings.FIREBASE_STORAGE_BUCKET},
        )
    else:
        _firebase_app = firebase_admin.get_app()
    return _firebase_app


def _guess_content_type(filename: str, default: str = "application/octet-stream") -> str:
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or default


def upload_file(file_obj, prefix: str, content_type: str | None = None) -> str:
    """
    Upload file-like object to Firebase Storage and return a public URL.
    """

    _initialize_app()
    bucket = storage.bucket()
    extension = ""
    if hasattr(file_obj, "name") and isinstance(file_obj.name, str) and "." in file_obj.name:
        extension = file_obj.name.rsplit(".", 1)[-1]
    blob_name = f"{prefix.rstrip('/')}/{uuid.uuid4().hex}.{extension or 'bin'}"
    blob = bucket.blob(blob_name)
    data = file_obj.read() if hasattr(file_obj, "read") else file_obj
    if content_type is None and hasattr(file_obj, "name"):
        content_type = _guess_content_type(file_obj.name)
    blob.upload_from_string(data, content_type=content_type)
    blob.make_public()
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)
    return blob.public_url


def upload_bytes(data: bytes, prefix: str, filename: str = "document.pdf", content_type: str | None = None) -> str:
    _initialize_app()
    file_obj = io.BytesIO(data)
    file_obj.name = filename
    content_type = content_type or _guess_content_type(filename, default="application/pdf")
    return upload_file(file_obj, prefix, content_type=content_type)
