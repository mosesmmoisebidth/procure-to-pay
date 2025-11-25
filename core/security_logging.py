import logging

security_log = logging.getLogger("security")


def log_login_success(request, user):
    security_log.info(
        "login_success",
        extra={
            "event": "login_success",
            "user_id": str(user.id),
            "username": user.get_username(),
            "ip": request.META.get("REMOTE_ADDR"),
        },
    )


def log_login_failure(request, username: str = ""):
    security_log.info(
        "login_failed",
        extra={
            "event": "login_failed",
            "username": username,
            "ip": request.META.get("REMOTE_ADDR"),
        },
    )


def log_request_approved(actor, purchase_request):
    security_log.info(
        "request_approved",
        extra={
            "event": "request_approved",
            "user_id": str(actor.id),
            "request_id": str(purchase_request.id),
            "status": purchase_request.status,
            "reference": purchase_request.reference,
        },
    )


def log_receipt_validation(actor, purchase_request, validation):
    security_log.info(
        "receipt_validated",
        extra={
            "event": "receipt_validated",
            "user_id": str(actor.id),
            "request_id": str(purchase_request.id),
            "is_match": validation.is_match,
            "score": validation.score,
        },
    )
