from argo.common.demo import DEMO_PRODUCTS, demo_id, demo_user

from .models import Product, StockMovement
from .stock import atomic


def seed() -> bool:
    """16 produtos de demonstração de duas lojas, com o movimento de estoque inicial."""
    if Product.objects.exists():
        return False
    with atomic():
        for key, sku, name, category, price, qty, seller in DEMO_PRODUCTS:
            owner = demo_user(seller)
            p = Product.objects.create(
                id=demo_id(key),
                seller_id=demo_id(seller),
                seller_name=owner["name"],
                sku=sku,
                name=name,
                description=f"{name}. Produto de demonstração da loja {owner['name']}.",
                category=category,
                price_cents=price,
                stock=qty,
            )
            if qty:
                StockMovement.objects.create(product=p, kind="IN", delta=qty, stock_after=qty, reason="Estoque inicial")
    return True
