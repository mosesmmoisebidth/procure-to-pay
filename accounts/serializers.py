from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Lightweight serializer exposing limited profile data to the frontend."""

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "full_name",
            "department",
            "role",
            "date_joined",
        )
        read_only_fields = ("id", "username", "email", "role", "date_joined")


class EmailOrUsernameAuthSerializer(serializers.Serializer):
    """Authenticate via either traditional username or email address."""

    email = serializers.CharField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    default_error_messages = {
        "invalid_credentials": "Unable to log in with provided credentials.",
    }

    def validate(self, attrs):
        identifier = attrs.get("email") or attrs.get("username")
        password = attrs.get("password")
        if not identifier:
            raise serializers.ValidationError({"email": "Enter your email or username."})
        if not password:
            raise serializers.ValidationError({"password": "Password is required."})

        username = identifier
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
            if not user:
                raise serializers.ValidationError(self.error_messages["invalid_credentials"])
            username = user.get_username()

        user = authenticate(
            request=self.context.get("request"),
            username=username,
            password=password,
        )
        if not user:
            raise serializers.ValidationError(self.error_messages["invalid_credentials"])
        attrs["user"] = user
        return attrs
