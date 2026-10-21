from rest_framework import serializers

from argo.common.validation import IntegerField

from .models import Order, OrderItem, OrderStatus, OrderStatusHistory


class CartLineSerializer(serializers.Serializer):
    product_id = serializers.CharField(help_text="7c2b1f0e-1d7a-5c55-9d8e-2f0b8a9c4d11")
    quantity = IntegerField(min_value=1, max_value=99, help_text="2")


class CheckoutSerializer(serializers.Serializer):
    items = CartLineSerializer(many=True, allow_empty=False, max_length=50)

    def validate_items(self, items: list[dict]) -> list[dict]:
        merged: dict[str, int] = {}
        for line in items:
            merged[line["product_id"]] = merged.get(line["product_id"], 0) + line["quantity"]
        return [{"product_id": k, "quantity": v} for k, v in merged.items()]


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "product_id",
            "seller_id",
            "seller_name",
            "sku",
            "product_name",
            "unit_price_cents",
            "quantity",
            "subtotal_cents",
        ]


class HistorySerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=OrderStatus.values)

    class Meta:
        model = OrderStatusHistory
        fields = ["status", "note", "actor", "created_at"]


class OrderSummarySerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True, help_text="AR-000042")
    status = serializers.ChoiceField(choices=OrderStatus.values)

    class Meta:
        model = Order
        fields = [
            "id",
            "code",
            "status",
            "customer_id",
            "customer_name",
            "total_cents",
            "items_count",
            "invoice_number",
            "created_at",
            "updated_at",
        ]


class OrderSerializer(OrderSummarySerializer):
    items = ItemSerializer(many=True, read_only=True)
    history = HistorySerializer(many=True, read_only=True)

    class Meta(OrderSummarySerializer.Meta):
        fields = [
            *OrderSummarySerializer.Meta.fields,
            "customer_email",
            "rejection_reason",
            "email_sent_at",
            "items",
            "history",
        ]


class OrderQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderStatus.values, required=False)
    q = serializers.CharField(required=False, allow_blank=True, help_text="Número do pedido (AR-000042 ou 42) ou nome do cliente")
    page = IntegerField(required=False, default=1)
    size = IntegerField(required=False, default=20)


class StatsQuerySerializer(serializers.Serializer):
    days = IntegerField(min_value=1, max_value=365, required=False, default=30)


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["SHIPPED", "DELIVERED"])
    note = serializers.CharField(
        max_length=300, required=False, allow_blank=True, default="", help_text="Código de rastreio BR123456789"
    )


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="", help_text="Comprei por engano")


class InternalEventSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["confirmed", "rejected", "invoiced", "email_sent", "released"])
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    invoice_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class DailyPointSerializer(serializers.Serializer):
    day = serializers.DateField()
    orders = IntegerField()
    revenue_cents = IntegerField()


class TopProductSerializer(serializers.Serializer):
    product_id = serializers.CharField()
    name = serializers.CharField()
    quantity = IntegerField()
    revenue_cents = IntegerField()


class StatsSerializer(serializers.Serializer):
    days = IntegerField()
    revenue_cents = IntegerField(help_text="Soma de pedidos confirmados, enviados e entregues")
    orders = IntegerField()
    average_ticket_cents = IntegerField()
    processing = IntegerField(help_text="Pedidos aguardando a fila")
    by_status = serializers.DictField(child=IntegerField())
    daily = DailyPointSerializer(many=True)
    top_products = TopProductSerializer(many=True)


class OrderPageSerializer(serializers.Serializer):
    items = OrderSummarySerializer(many=True)
    page = IntegerField()
    size = IntegerField()
    total = IntegerField()
