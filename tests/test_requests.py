from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from procurement_app.models import PurchaseRequest
from django.contrib.auth import get_user_model


class PurchaseRequestTests(APITestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff",
            email="staff@example.com",
            password="pass1234",
            role="staff",
        )
        token = Token.objects.create(user=self.staff)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.url = reverse("requests-list")

    def _sample_file(self, name="proforma.pdf", size=1024):
        return SimpleUploadedFile(name, b"x" * size, content_type="application/pdf")

    @patch("procurement_app.views.extraction_service.extract_document")
    def test_create_purchase_request(self, mock_extract):
        mock_extract.return_value = None
        payload = {
            "title": "Laptops",
            "description": "Procure laptops",
            "amount_estimated": "1200",
            "currency": "USD",
            "needed_by": "2025-12-31",
            "notes": "Urgent",
        }
        response = self.client.post(self.url, {**payload, "proforma_file": self._sample_file()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(PurchaseRequest.objects.filter(title="Laptops").exists())

    @patch("procurement_app.views.extraction_service.extract_document")
    def test_duplicate_pending_request_blocked(self, mock_extract):
        mock_extract.return_value = None
        data = {
            "title": "Servers",
            "description": "First request",
            "amount_estimated": "5000",
            "currency": "USD",
            "proforma_file": self._sample_file(),
        }
        self.client.post(self.url, data, format="multipart")
        dup = {
            "title": "Servers",
            "description": "Duplicate",
            "amount_estimated": "5000",
            "currency": "USD",
            "proforma_file": self._sample_file(name="dup.pdf"),
        }
        response = self.client.post(self.url, dup, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    @override_settings(MAX_UPLOAD_SIZE=10)
    @patch("procurement_app.views.extraction_service.extract_document")
    def test_upload_too_large_rejected(self, mock_extract):
        large_file = self._sample_file(size=20)
        payload = {
            "title": "Huge document",
            "description": "Test",
            "amount_estimated": "100",
            "currency": "USD",
            "proforma_file": large_file,
        }
        response = self.client.post(self.url, payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
