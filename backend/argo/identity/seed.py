from argo.common.demo import DEMO_PASSWORD, DEMO_USERS, demo_id

from .models import User
from .services import hash_password


def seed() -> bool:
    """Contas de demonstração (todas com a senha Argo@2026)."""
    if User.objects.exists():
        return False
    hashed = hash_password(DEMO_PASSWORD)
    User.objects.bulk_create(
        [User(id=demo_id(u["key"]), name=u["name"], email=u["email"], password_hash=hashed, role=u["role"]) for u in DEMO_USERS]
    )
    return True
