import logging
from typing import Iterable

import resend
from django.conf import settings
from django.contrib.auth import get_user_model

from procurement_app.models import PurchaseRequest

User = get_user_model()
logger = logging.getLogger("procure_to_pay")


def _valid_recipients(emails: Iterable[str | None]) -> list[str]:
    return [email for email in emails if email]


def _from_identity() -> str | None:
    sender = settings.RESEND_FROM_EMAIL
    if not sender:
        return None
    if "<" in sender:
        return sender
    return f"Procure-to-Pay <{sender}>"


def _send_email(subject: str, text: str, html: str, recipients: Iterable[str | None]) -> None:
    api_key = settings.RESEND_API_KEY
    sender = _from_identity()
    to = _valid_recipients(recipients)
    if not (api_key and sender and to):
        logger.debug("Skipping email send; Resend not configured or no recipients.")
        return
    resend.api_key = api_key
    payload = {
        "from": sender,
        "to": to,
        "subject": subject,
        "text": text,
        "html": html,
        "reply_to": sender,
    }
    try:
        resend.Emails.send(payload)
        logger.info("Sent notification email '%s' to %s", subject, to)
    except Exception:
        logger.exception("Failed to send email via Resend.")


def _format_request_details(request_obj: PurchaseRequest) -> tuple[str, str]:
    html = (
        "<ul>"
        f"<li><strong>Title:</strong> {request_obj.title}</li>"
        f"<li><strong>Reference:</strong> {request_obj.reference}</li>"
        f"<li><strong>Status:</strong> {request_obj.get_status_display()}</li>"
        f"<li><strong>Amount:</strong> {request_obj.amount_estimated} {request_obj.currency or ''}</li>"
        f"<li><strong>Vendor:</strong> {request_obj.vendor_name or 'N/A'}</li>"
        "</ul>"
    )
    text = (
        f"- Title: {request_obj.title}\n"
        f"- Reference: {request_obj.reference}\n"
        f"- Status: {request_obj.get_status_display()}\n"
        f"- Amount: {request_obj.amount_estimated} {request_obj.currency or ''}\n"
        f"- Vendor: {request_obj.vendor_name or 'N/A'}"
    )
    return text, html


def _staff_email(request_obj: PurchaseRequest) -> list[str]:
    return _valid_recipients([getattr(request_obj.created_by, "email", None)])


def notify_intermediate_approval(request_obj: PurchaseRequest, approver: User, next_level_role: str | None) -> None:
    recipients = _staff_email(request_obj)
    if next_level_role:
        recipients.extend(_get_role_emails(next_level_role))
    if not recipients:
        return
    subject = f"Purchase Request {request_obj.reference} approved by {approver.get_full_name() or approver.username}"
    text_details, html_details = _format_request_details(request_obj)
    text = (
        f"Hello,\n\n"
        f"{approver.get_full_name() or approver.username} approved the request at level {request_obj.current_approval_level}.\n"
        "The next approver has been notified.\n\n"
        f"{text_details}\n\n"
        "This is an automated message from the Procure-to-Pay system."
    )
    html = (
        "<p>Hello,</p>"
        f"<p>{approver.get_full_name() or approver.username} approved the request at level {request_obj.current_approval_level}."
        " The next approver has been notified.</p>"
        f"{html_details}"
        "<p>This is an automated message from the Procure-to-Pay system.</p>"
    )
    _send_email(subject, text, html, recipients)


def notify_final_approval(request_obj: PurchaseRequest, approver: User) -> None:
    recipients = _staff_email(request_obj)
    recipients.extend(_get_role_emails(User.Roles.FINANCE))
    if not recipients:
        return
    subject = f"Purchase Request {request_obj.reference} fully approved"
    text_details, html_details = _format_request_details(request_obj)
    text = (
        "Hello,\n\n"
        f"{approver.get_full_name() or approver.username} approved the final level for this request.\n"
        "Purchase order generation is complete. Finance can now track receipts.\n\n"
        f"{text_details}\n\n"
        "This is an automated message from the Procure-to-Pay system."
    )
    html = (
        "<p>Hello,</p>"
        f"<p>{approver.get_full_name() or approver.username} approved the final level for this request."
        " Purchase order generation is complete. Finance can now track receipts.</p>"
        f"{html_details}"
        "<p>This is an automated message from the Procure-to-Pay system.</p>"
    )
    _send_email(subject, text, html, recipients)


def notify_rejection(request_obj: PurchaseRequest, approver: User, comment: str) -> None:
    recipients = _staff_email(request_obj)
    if not recipients:
        return
    subject = f"Purchase Request {request_obj.reference} rejected"
    text_details, html_details = _format_request_details(request_obj)
    text = (
        "Hello,\n\n"
        f"{approver.get_full_name() or approver.username} rejected the request.\n"
        f"Reason: {comment or 'Not provided.'}\n\n"
        f"{text_details}\n\n"
        "Please review and resubmit if necessary.\n"
        "This is an automated message from the Procure-to-Pay system."
    )
    html = (
        "<p>Hello,</p>"
        f"<p>{approver.get_full_name() or approver.username} rejected the request.</p>"
        f"<p><strong>Reason:</strong> {comment or 'Not provided.'}</p>"
        f"{html_details}"
        "<p>Please review and resubmit if necessary.</p>"
        "<p>This is an automated message from the Procure-to-Pay system.</p>"
    )
    _send_email(subject, text, html, recipients)


def _get_role_emails(role: str) -> list[str]:
    users = User.objects.filter(role=role).exclude(email__isnull=True).exclude(email__exact="")
    return [user.email for user in users]
