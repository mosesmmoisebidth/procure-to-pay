from django.utils.deprecation import MiddlewareMixin

from .log_context import request_id_ctx, user_id_ctx


class RequestContextMiddleware(MiddlewareMixin):
    """
    Stores request_id and user_id in contextvars so log records can access them.
    """

    def process_request(self, request):
        request_id_ctx.set(getattr(request, "request_id", "-"))
        if getattr(request, "user", None) and request.user.is_authenticated:
            user_id_ctx.set(str(request.user.id))
        else:
            user_id_ctx.set("-")

    def process_response(self, request, response):
        request_id_ctx.set("-")
        user_id_ctx.set("-")
        return response
