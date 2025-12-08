from rest_framework import permissions


class IsRole(permissions.BasePermission):
    """Allow access only to users with one of the expected roles."""

    allowed_roles: tuple[str, ...] = tuple()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not self.allowed_roles:
            return True
        return request.user.role in self.allowed_roles


class IsStaff(IsRole):
    allowed_roles = ("staff",)


class IsApproverLevel1(IsRole):
    allowed_roles = ("approver_lvl1",)


class IsApproverLevel2(IsRole):
    allowed_roles = ("approver_lvl2",)


class IsFinance(IsRole):
    allowed_roles = ("finance",)
