"""Write access to a process's institute entries: the process assignee or an admin (§7.2)."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsEntryEditorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin or obj.process.assigned_lawyer_id == request.user.id
