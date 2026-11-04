import uuid
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar("argo_request_id", default="")


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def current_request_id() -> str:
    return request_id.get()
