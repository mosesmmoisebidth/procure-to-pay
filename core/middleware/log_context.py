import logging
from contextvars import ContextVar

request_id_ctx = ContextVar("request_id", default="-")
user_id_ctx = ContextVar("user_id", default="-")


class LogContextFilter(logging.Filter):
    """
    Injects request_id and user_id into log records so they appear in JSON logs.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        record.user_id = user_id_ctx.get()
        return True
