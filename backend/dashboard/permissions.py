from accounts.models import UserType
from rest_framework.permissions import BasePermission


class IsAdminOrSuperuser(BasePermission):
    """
    Grants access only to users whose `type` is ADMIN or SUPERUSER.
    Works with the custom UserType defined in accounts.models.
    """

    message = "Admin privileges are required to access this resource."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.type in (UserType.ADMIN, UserType.SUPERUSER)
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: grants access to the owner of the resource
    or any admin / superuser.
    The model instance must have a `user` attribute.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.type in (UserType.ADMIN, UserType.SUPERUSER):
            return True
        return getattr(obj, "user", None) == request.user
