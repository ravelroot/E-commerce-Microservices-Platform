import uuid
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


def client_ip(request) -> str | None:
    for header in ("X-Real-IP", "X-Forwarded-For"):
        value = request.headers.get(header, "")
        if value:
            return value.split(",")[0].strip()[:45] or None
    return (request.META.get("REMOTE_ADDR") or "")[:45] or None


def user_agent(request) -> str:
    return (request.headers.get("User-Agent") or "")[:200]
