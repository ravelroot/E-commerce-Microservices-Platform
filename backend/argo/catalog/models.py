from django.db import models
from django.db.models import F, Q

from argo.common.utils import new_id, utcnow

MOVEMENT_KINDS = ("IN", "OUT", "COUNT", "SALE", "RELEASE")


class Product(models.Model):
    id = models.CharField(primary_key=True, max_length=36, default=new_id)
    seller_id = models.CharField(max_length=36)
    seller_name = models.CharField(max_length=120)
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=140)
    description = models.TextField(default="", blank=True)
    category = models.CharField(max_length=60)
    price_cents = models.IntegerField()
    stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=utcnow)
    updated_at = models.DateTimeField(default=utcnow)

    class Meta:
        db_table = "products"
        constraints = [
            models.CheckConstraint(condition=Q(stock__gte=0), name="ck_products_stock_non_negative"),
            models.CheckConstraint(condition=Q(price_cents__gt=0), name="ck_products_price_positive"),
        ]
        indexes = [
            models.Index(fields=["seller_id"], name="ix_products_seller"),
            models.Index(fields=["category"], name="ix_products_category"),
        ]

    def save(self, *args, **kwargs):
        self.updated_at = utcnow()
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "updated_at"}
        super().save(*args, **kwargs)

    @property
    def is_low(self) -> bool:
        return self.stock <= self.low_stock_threshold

    def __str__(self) -> str:
        return f"{self.sku} · {self.name}"


class StockMovement(models.Model):
    """Livro-razão do estoque: cada entrada, saída, contagem, venda ou devolução vira uma linha imutável."""

    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.DB_CASCADE, related_name="movements", db_index=False)
    kind = models.CharField(max_length=10)
    delta = models.IntegerField()
    stock_after = models.IntegerField()
    reason = models.CharField(max_length=200, default="", blank=True)
    order_id = models.BigIntegerField(null=True, blank=True)
    actor_id = models.CharField(max_length=36, null=True, blank=True)
    created_at = models.DateTimeField(default=utcnow)

    class Meta:
        db_table = "stock_movements"
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=MOVEMENT_KINDS), name="ck_stock_movements_kind"),
            models.UniqueConstraint(fields=["order_id", "product", "kind"], name="uq_stock_movements_order_product_kind"),
        ]
        indexes = [models.Index(fields=["product", "created_at"], name="ix_movements_product_created")]


LOW_STOCK = Q(stock__lte=F("low_stock_threshold"))
