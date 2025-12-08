from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.security_logging import log_login_failure, log_login_success
from core.throttling import LoginThrottle

from .serializers import EmailOrUsernameAuthSerializer, UserSerializer


@method_decorator(csrf_exempt, name="dispatch")
class CustomAuthToken(ObtainAuthToken):
    """Return a DRF token plus basic user info."""

    serializer_class = EmailOrUsernameAuthSerializer
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            log_login_failure(request, request.data.get("email") or request.data.get("username") or "")
            raise
        user = serializer.validated_data['user']
        log_login_success(request, user)
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
            }
        )


class CurrentUserView(APIView):
    """Return the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class LogoutView(APIView):
    """Invalidate the current token so the session fully terminates."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
