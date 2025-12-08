from __future__ import annotations

from typing import Dict, List

from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONOpenAPIRenderer
from rest_framework.response import Response
from rest_framework.schemas.openapi import SchemaGenerator
from rest_framework.views import APIView


class TaggedSchemaGenerator(SchemaGenerator):
    """Schema generator that attaches semantic tags to each path."""

    TAG_RULES: List[tuple[str, str]] = [
        ("Authentication", "/api/auth/"),
        ("Purchase Requests", "/api/requests"),
        ("Finance", "/api/finance/"),
    ]
    DEFAULT_TAG = "Misc"

    def _tag_for_path(self, path: str) -> str:
        normalized = "/" + path.lstrip("/")
        for tag, prefix in self.TAG_RULES:
            normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
            if normalized.startswith(normalized_prefix):
                return tag
        return self.DEFAULT_TAG

    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request=request, public=public)
        if not schema:
            return schema

        tags_meta: Dict[str, Dict[str, str]] = {}
        for tag_name, _ in self.TAG_RULES:
            tags_meta.setdefault(tag_name, {"name": tag_name})
        tags_meta.setdefault(self.DEFAULT_TAG, {"name": self.DEFAULT_TAG})

        for path, methods in schema.get("paths", {}).items():
            tag = self._tag_for_path(path)
            for method_data in methods.values():
                method_data["tags"] = [tag]

        schema["tags"] = list(tags_meta.values())
        return schema


class TaggedSchemaView(APIView):
    """OpenAPI schema endpoint that everyone can access."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    renderer_classes = [JSONOpenAPIRenderer]
    generator_class = TaggedSchemaGenerator

    def get(self, request, *args, **kwargs):
        generator = self.generator_class(
            title="Smart Procure-to-Pay API",
            description="API documentation grouped by authentication, procurement workflow, and finance operations.",
            version="1.0.0",
        )
        schema = generator.get_schema(request=request, public=True)
        if not schema:
            return Response(status=404)
        return Response(schema)
