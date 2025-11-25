import uuid

from django.utils.deprecation import MiddlewareMixin


class RequestIdMiddleware(MiddlewareMixin):
    """
    Ensures every request has a request_id; reuses X-Request-ID header if provided.
    """

    header_name = "X-Request-ID"

    def process_request(self, request):
        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.request_id = request_id

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", None)
        if request_id:
            response[self.header_name] = request_id
        return response
