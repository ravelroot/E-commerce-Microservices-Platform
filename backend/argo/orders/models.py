from django.db import models
from django.db.models import Q

from argo.common.utils import utcnow

STATUSES = ("PENDING", "CONFIRMED", "REJECTED", "SHIPPED", "DELIVERED", "CANCELED")


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Aguardando a fila"
    CONFIRMED = "CONFIRMED", "Confirmado"
    REJECTED = "REJECTED", "Recusado"
    SHIPPED = "SHIPPED", "Enviado"
    DELIVERED = "DELIVERED", "Entregue"
    CANCELED = "CANCELED", "Cancelado"


class Order(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer_id = models.CharField(max_length=36)
    customer_name = models.CharField(max_length=120)
    customer_email = models.CharField(max_length=160)
    status = models.CharField(max_length=12, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    total_cents = models.IntegerField()
    items_count = models.IntegerField()
    rejection_reason = models.CharField(max_length=300, null=True, blank=True)
    invoice_number = models.CharField(max_length=30, null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=utcnow)
    updated_at = models.DateTimeField(default=utcnow)

    class Meta:
        db_table = "orders"
        constraints = [
            models.CheckConstraint(condition=Q(status__in=STATUSES), name="ck_orders_status"),
            models.CheckConstraint(condition=Q(total_cents__gte=0), name="ck_orders_total"),
        ]
        indexes = [
            models.Index(fields=["customer_id", "created_at"], name="ix_orders_customer_created"),
            models.Index(fields=["status"], name="ix_orders_status"),
        ]

    @property
    def code(self) -> str:
        return f"AR-{self.id:06d}"

    def __str__(self) -> str:
        return self.code


class OrderItem(models.Model):
    """Foto do produto no momento da compra: preço e nome não mudam se o catálogo mudar depois."""

    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.DB_CASCADE, related_name="items", db_index=False)
    product_id = models.CharField(max_length=36)
    seller_id = models.CharField(max_length=36)
    seller_name = models.CharField(max_length=120)
    sku = models.CharField(max_length=40)
    product_name = models.CharField(max_length=140)
    unit_price_cents = models.IntegerField()
    quantity = models.IntegerField()
    subtotal_cents = models.IntegerField()

    class Meta:
        db_table = "order_items"
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="ck_order_items_quantity")]
        indexes = [
            models.Index(fields=["seller_id"], name="ix_order_items_seller"),
            models.Index(fields=["order"], name="ix_order_items_order"),
        ]


class OrderStatusHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.DB_CASCADE, related_name="history", db_index=False)
    status = models.CharField(max_length=12)
    note = models.CharField(max_length=300, default="", blank=True)
    actor = models.CharField(max_length=120, default="Sistema")
    created_at = models.DateTimeField(default=utcnow)

    class Meta:
        db_table = "order_status_history"
        indexes = [models.Index(fields=["order"], name="ix_order_status_history_order")]
