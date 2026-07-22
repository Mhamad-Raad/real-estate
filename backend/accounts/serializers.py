"""Serializers for auth and the current-user profile."""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Public shape of the authenticated user (the `me` payload)."""

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_admin",
        )
        read_only_fields = ("id", "username", "role", "is_admin")


class LoginSerializer(TokenObtainPairSerializer):
    """Adds the user profile alongside the access/refresh tokens on login."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
