"""Server-side RBAC — the real authorization boundary (never UI hiding) (§7.2)."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    """Admin-only endpoints (users, category writes, duplicate override, reports, activities)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsAdminOrReadOnly(BasePermission):
    """Everyone authenticated may read; only admins may write (e.g. categories)."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or request.user.is_admin


class IsProcessAssigneeOrAdmin(BasePermission):
    """Edit/soft-delete a Process only if you are its process-wide `assigned_lawyer` (or admin).

    Being a per-institute assignee grants nothing here — that distinction is deliberate (§7.2).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_admin:
            return True
        return getattr(obj, "assigned_lawyer_id", None) == request.user.id
