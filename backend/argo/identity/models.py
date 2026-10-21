from django.db import models
from django.db.models import Q

from argo.common.utils import new_id, utcnow

ROLES = (("ADMIN", "Administrador"), ("SELLER", "Vendedor"), ("CUSTOMER", "Cliente"))


class User(models.Model):
    id = models.CharField(primary_key=True, max_length=36, default=new_id)
    name = models.CharField(max_length=120)
    email = models.CharField(max_length=160, unique=True)
    password_hash = models.CharField(max_length=128)
    role = models.CharField(max_length=12, choices=ROLES, default="CUSTOMER")
    active = models.BooleanField(default=True)
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=utcnow)
    updated_at = models.DateTimeField(default=utcnow)

    class Meta:
        db_table = "users"
        constraints = [models.CheckConstraint(condition=Q(role__in=["ADMIN", "SELLER", "CUSTOMER"]), name="ck_users_role")]

    def save(self, *args, **kwargs):
        self.updated_at = utcnow()
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "updated_at"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email


class RefreshToken(models.Model):
    """Refresh token opaco de uso único. Só o SHA-256 fica no banco; a família permite detectar reuso."""

    id = models.CharField(primary_key=True, max_length=36, default=new_id)
    user = models.ForeignKey(User, on_delete=models.DB_CASCADE, related_name="tokens", db_index=False)
    family_id = models.CharField(max_length=36)
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=utcnow)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    replaced_by = models.CharField(max_length=36, null=True, blank=True)

    class Meta:
        db_table = "refresh_tokens"
        indexes = [
            models.Index(fields=["family_id"], name="ix_refresh_tokens_family"),
            models.Index(fields=["user"], name="ix_refresh_tokens_user_id"),
        ]
