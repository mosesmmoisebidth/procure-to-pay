from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from procurement_app.models import Approval, PurchaseRequest

from . import po_generation, notifications

User = get_user_model()


class WorkflowError(Exception):
    """Raised when an approval action violates workflow constraints."""


ROLE_BY_LEVEL = {
    1: User.Roles.APPROVER_L1,
    2: User.Roles.APPROVER_L2,
}


def _validate_user_for_level(user, level: int) -> None:
    expected_role = ROLE_BY_LEVEL.get(level)
    if not expected_role:
        return
    if user.role != expected_role:
        raise WorkflowError(
            f"User {user} is not allowed to approve level {level} (needs {expected_role})."
        )


def _clean_comment(comment: str | None) -> str:
    if comment is None:
        return ""
    normalized = str(comment).strip()
    if normalized.lower() in {"", "string", "null"}:
        return ""
    return normalized


def _decrement_required_levels(request_obj: PurchaseRequest) -> int:
    remaining = max(request_obj.required_approval_levels - 1, 0)
    request_obj.required_approval_levels = remaining
    return remaining


@transaction.atomic
def approve_request(purchase_request_id, user: User, comment: str = "") -> PurchaseRequest:
    """Approve the purchase request at the user's level and advance the workflow."""

    request_obj = (
        PurchaseRequest.objects.select_for_update()
        .select_related("created_by")
        .get(pk=purchase_request_id)
    )

    if request_obj.status != PurchaseRequest.Status.PENDING:
        raise WorkflowError("Only pending requests can be approved.")

    level = request_obj.current_approval_level
    _validate_user_for_level(user, level)

    clean_comment = _clean_comment(comment)
    Approval.objects.create(
        purchase_request=request_obj,
        approver=user,
        level=level,
        decision=Approval.Decision.APPROVED,
        comment=clean_comment,
    )

    remaining = _decrement_required_levels(request_obj)
    update_fields = ["required_approval_levels", "updated_at"]

    if remaining == 0:
        request_obj.status = PurchaseRequest.Status.APPROVED
        request_obj.current_approval_level = level
        update_fields.extend(["status", "current_approval_level"])
        request_obj.save(update_fields=update_fields)
        po_generation.ensure_purchase_order_exists(request_obj)
    else:
        request_obj.current_approval_level = min(request_obj.current_approval_level + 1, level + 1)
        update_fields.append("current_approval_level")
        request_obj.save(update_fields=update_fields)
        next_role = ROLE_BY_LEVEL.get(request_obj.current_approval_level)
        notifications.notify_intermediate_approval(request_obj, user, next_role)
        return request_obj

    notifications.notify_final_approval(request_obj, user)
    return request_obj


@transaction.atomic
def reject_request(purchase_request_id, user: User, comment: str = "") -> PurchaseRequest:
    """Reject the purchase request and stop the workflow."""

    request_obj = (
        PurchaseRequest.objects.select_for_update()
        .select_related("created_by")
        .get(pk=purchase_request_id)
    )

    if request_obj.status != PurchaseRequest.Status.PENDING:
        raise WorkflowError("Only pending requests can be rejected.")

    level = request_obj.current_approval_level
    _validate_user_for_level(user, level)

    clean_comment = _clean_comment(comment)
    Approval.objects.create(
        purchase_request=request_obj,
        approver=user,
        level=level,
        decision=Approval.Decision.REJECTED,
        comment=clean_comment,
    )

    request_obj.status = PurchaseRequest.Status.REJECTED
    request_obj.updated_at = timezone.now()
    request_obj.required_approval_levels = 0
    request_obj.save(update_fields=["status", "required_approval_levels", "updated_at"])
    notifications.notify_rejection(request_obj, user, clean_comment)
    return request_obj
