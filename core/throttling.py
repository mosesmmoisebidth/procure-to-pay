from rest_framework.throttling import SimpleRateThrottle


class LoginThrottle(SimpleRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return f"throttle_login_ip_{ident}"


class HeavyActionThrottle(SimpleRateThrottle):
    scope = "heavy_action"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return f"throttle_heavy_user_{user.pk}"
        return f"throttle_heavy_ip_{self.get_ident(request)}"
