import re

from rest_framework import serializers

from argo.common.validation import IntegerField

from .models import Product, StockMovement

SORTS = ["name", "price_asc", "price_desc", "newest", "stock"]


def clean(value: str) -> str:
    return " ".join(value.split())


class ProductSerializer(serializers.ModelSerializer):
    price_cents = IntegerField(help_text="Preço em centavos (6290 = R$ 62,90)")
    version = IntegerField(help_text="Versão para controle de concorrência otimista")

    class Meta:
        model = Product
        fields = [
            "id",
            "seller_id",
            "seller_name",
            "sku",
            "name",
            "description",
            "category",
            "price_cents",
            "stock",
            "low_stock_threshold",
            "active",
            "version",
            "created_at",
            "updated_at",
        ]


class ProductCreateSerializer(serializers.Serializer):
    sku = serializers.CharField(min_length=3, max_length=40, help_text="LOJ-CAM-01")
    name = serializers.CharField(min_length=2, max_length=140, help_text="Camiseta de algodão")
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    category = serializers.CharField(min_length=2, max_length=60, help_text="Vestuário")
    price_cents = IntegerField(min_value=1, max_value=100_000_000, help_text="7990")
    stock = IntegerField(min_value=0, max_value=1_000_000, required=False, default=0, help_text="Estoque inicial")
    low_stock_threshold = IntegerField(min_value=0, max_value=10_000, required=False, default=5)

    def validate_sku(self, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9\-_.]+", value):
            raise serializers.ValidationError("Use só letras, números, hífen, ponto ou sublinhado.")
        return value.upper()

    def validate_name(self, value: str) -> str:
        return clean(value)

    def validate_category(self, value: str) -> str:
        return clean(value)


class ProductUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=140, required=False, allow_null=True)
    description = serializers.CharField(max_length=2000, required=False, allow_null=True, allow_blank=True)
    category = serializers.CharField(min_length=2, max_length=60, required=False, allow_null=True)
    price_cents = IntegerField(min_value=1, max_value=100_000_000, required=False, allow_null=True)
    low_stock_threshold = IntegerField(min_value=0, max_value=10_000, required=False, allow_null=True)
    active = serializers.BooleanField(required=False, allow_null=True)
    version = IntegerField(
        required=False,
        allow_null=True,
        help_text="Se enviado, a alteração só é aplicada se a versão bater (409 caso contrário)",
    )


class ProductQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, help_text="Busca por nome, SKU ou vendedor")
    category = serializers.CharField(required=False, allow_blank=True)
    seller_id = serializers.CharField(required=False, allow_blank=True)
    mine = serializers.BooleanField(required=False, default=False, help_text="Somente produtos do vendedor logado")
    include_inactive = serializers.BooleanField(
        required=False, default=False, help_text="Inclui inativos (só vendedor dono ou administrador)"
    )
    low_stock = serializers.BooleanField(
        required=False, default=False, help_text="Somente com estoque no limite mínimo ou abaixo"
    )
    sort = serializers.ChoiceField(choices=SORTS, required=False, default="name")
    page = IntegerField(required=False, default=1)
    size = IntegerField(required=False, default=20)


class PageQuerySerializer(serializers.Serializer):
    page = IntegerField(required=False, default=1)
    size = IntegerField(required=False, default=20)


class StockAdjustSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=["IN", "OUT", "COUNT"], help_text="IN soma, OUT subtrai e COUNT define o valor contado no inventário"
    )
    quantity = IntegerField(min_value=0, max_value=1_000_000, help_text="10")
    reason = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default="", help_text="Reposição do fornecedor"
    )


class MovementSerializer(serializers.ModelSerializer):
    product_id = serializers.CharField()

    class Meta:
        model = StockMovement
        fields = ["id", "product_id", "kind", "delta", "stock_after", "reason", "order_id", "created_at"]


class CategoryCountSerializer(serializers.Serializer):
    name = serializers.CharField()
    products = IntegerField()


class StockSummarySerializer(serializers.Serializer):
    products = IntegerField()
    units = IntegerField()
    low_stock = IntegerField()
    out_of_stock = IntegerField()
    inventory_value_cents = IntegerField()


class LookupSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.CharField(), min_length=1, max_length=100)


class ProductSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "sku", "name", "price_cents", "stock", "active", "seller_id", "seller_name"]


class StockLineSerializer(serializers.Serializer):
    product_id = serializers.CharField()
    quantity = IntegerField(min_value=1)


class StockCommitSerializer(serializers.Serializer):
    order_id = IntegerField()
    items = StockLineSerializer(many=True, allow_empty=False)


class ShortageSerializer(serializers.Serializer):
    product_id = serializers.CharField()
    name = serializers.CharField()
    requested = IntegerField()
    available = IntegerField()


class StockCommitResultSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    already_processed = serializers.BooleanField()
    shortages = ShortageSerializer(many=True)


class StockReleaseSerializer(serializers.Serializer):
    order_id = IntegerField()


class StockReleaseResultSerializer(serializers.Serializer):
    released = IntegerField(help_text="Quantidade de produtos devolvidos ao estoque")


class ProductPageSerializer(serializers.Serializer):
    items = ProductSerializer(many=True)
    page = IntegerField()
    size = IntegerField()
    total = IntegerField()


class MovementPageSerializer(serializers.Serializer):
    items = MovementSerializer(many=True)
    page = IntegerField()
    size = IntegerField()
    total = IntegerField()
