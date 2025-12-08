from django.views.generic import TemplateView


def get_swagger_view(title: str = "API documentation", schema_url: str = "/api/schema/"):
    """
    Return a Django view that renders a Swagger UI powered by the generated OpenAPI schema.

    This minimal wrapper mimics the historical django-rest-swagger API and is scoped to this project.
    """

    class SwaggerUIView(TemplateView):
        template_name = "swagger/index.html"

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context.update(
                {
                    "title": title,
                    "schema_url": schema_url,
                }
            )
            return context

    return SwaggerUIView.as_view()
