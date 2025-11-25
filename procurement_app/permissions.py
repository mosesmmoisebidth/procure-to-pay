from rest_framework import permissions

from procurement_app.models import PurchaseRequest


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Staff members can manage only their own pending requests."""

    def has_object_permission(self, request, view, obj: PurchaseRequest):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.created_by_id == request.user.id and obj.status == PurchaseRequest.Status.PENDING
