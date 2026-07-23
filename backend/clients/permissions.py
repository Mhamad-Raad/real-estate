"""Client write access: admin, or a lawyer assigned to one of the client's processes (§4.2)."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsClientEditorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_admin:
            return True
        # The lawyer who created the client may edit it, even before a process links them.
        if obj.created_by_id == request.user.id:
            return True
        from processes.models import Process

        return Process.objects.filter(client=obj, assigned_lawyer=request.user).exists()
