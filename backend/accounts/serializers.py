"""Serializers for auth and the current-user profile."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User
from .selectors import assignable_lawyers


class AssignableLawyerField(serializers.PrimaryKeyRelatedField):
    """A lawyer a case may actually be given to — deactivated and soft-deleted users are refused.

    `assigned_lawyer` is deliberately not editable afterwards (§7.2), so accepting someone who has
    left would strand the case with an assignee who can never open it. The queryset is evaluated
    per request because a user may be deactivated while a form sits open.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("queryset", assignable_lawyers())
        super().__init__(**kwargs)

    def get_queryset(self):
        return assignable_lawyers()


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


class AdminUserSerializer(serializers.ModelSerializer):
    """Admin-managed user record: create/edit accounts, set role, reset password (§4, §7)."""

    # Write-only: accepted on create/update but never echoed back.
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
            "is_admin",
            "password",
            "version",
        )
        read_only_fields = ("id", "is_admin", "version")

    def validate_password(self, value):
        validate_password(value)  # Django's configured strength checks
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "Password is required for a new user."})
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(TokenObtainPairSerializer):
    """Adds the user profile alongside the access/refresh tokens on login."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
