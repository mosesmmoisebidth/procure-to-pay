class ContentSecurityPolicyMiddleware:
    """Applies a very restrictive default Content-Security-Policy header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", "default-src 'self'")
        return response
