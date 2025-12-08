class ContentSecurityPolicyMiddleware:
    """
    Applies a strict CSP by default, but relaxes it for Swagger docs
    so that Swagger UI can load its JS/CSS from jsDelivr and run the
    inline init script/styles.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path or ""

        # Adjust these prefixes if your docs are under a different URL
        is_swagger_docs = (
            path.startswith("/docs")      # e.g. /docs/ or /docs/swagger/
            or path.startswith("/swagger")
            or path.startswith("/api/docs")
        )

        if is_swagger_docs:
            # Relaxed CSP for Swagger UI only
            csp = (
                "default-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'self'; "
                # Allow styles from self + jsDelivr + inline
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                # Allow scripts from self + jsDelivr + inline
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            )
        else:
            # Strict CSP for the rest of the app
            csp = (
                "default-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'self'; "
                "style-src 'self'; "
                "script-src 'self'; "
            )

        # Always set/override CSP header explicitly
        response["Content-Security-Policy"] = csp
        return response
