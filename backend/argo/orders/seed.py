import random
from datetime import timedelta

from argo.common.demo import DEMO_PRODUCTS, demo_id, demo_user
from argo.common.utils import utcnow

from .models import Order, OrderItem, OrderStatusHistory
from .services import atomic

CUSTOMERS = ["cliente", "c1", "c2", "c3", "c4"]


def seed(count: int = 64) -> bool:
    """Histórico de 30 dias para os painéis (sempre o mesmo, semente 2026)."""
    if Order.objects.exists():
        return False
    rnd = random.Random(2026)
    now = utcnow()
    catalog = [p for p in DEMO_PRODUCTS if p[5] > 0]
    ages = sorted((timedelta(days=rnd.uniform(0.2, 29.5), minutes=rnd.randint(0, 600)) for _ in range(count)), reverse=True)
    with atomic():
        for age in ages:
            created = now - age
            customer = demo_user(rnd.choice(CUSTOMERS))
            if age.days > 9:
                status = rnd.choices(["DELIVERED", "CANCELED"], [0.9, 0.1])[0]
            elif age.days > 3:
                status = rnd.choices(["SHIPPED", "DELIVERED", "CANCELED"], [0.5, 0.4, 0.1])[0]
            else:
                status = rnd.choices(["CONFIRMED", "SHIPPED", "REJECTED"], [0.65, 0.25, 0.1])[0]
            items = []
            for key, sku, name, _cat, price, _stock, seller in rnd.sample(catalog, rnd.choice([1, 1, 2, 2, 3])):
                qty = rnd.choice([1, 1, 1, 2, 3])
                items.append(
                    OrderItem(
                        product_id=demo_id(key),
                        seller_id=demo_id(seller),
                        seller_name=demo_user(seller)["name"],
                        sku=sku,
                        product_name=name,
                        unit_price_cents=price,
                        quantity=qty,
                        subtotal_cents=price * qty,
                    )
                )
            order = Order(
                customer_id=demo_id(customer["key"]),
                customer_name=customer["name"],
                customer_email=customer["email"],
                status=status,
                total_cents=sum(i.subtotal_cents for i in items),
                items_count=sum(i.quantity for i in items),
                created_at=created,
                updated_at=created,
                email_sent_at=created + timedelta(seconds=3) if status != "REJECTED" else None,
            )
            steps = [("PENDING", "Pedido recebido. Reservando estoque.", customer["name"], 0)]
            if status == "REJECTED":
                order.rejection_reason = "Estoque insuficiente no momento da reserva."
                steps.append(("REJECTED", order.rejection_reason, "Fila de pedidos", 2))
            else:
                steps.append(("CONFIRMED", "Estoque reservado e pedido confirmado.", "Fila de pedidos", 2))
                if status in ("SHIPPED", "DELIVERED"):
                    steps.append(("SHIPPED", f"Código de rastreio BR{rnd.randint(10**8, 10**9 - 1)}BR", "Loja", 60 * 26))
                if status == "DELIVERED":
                    steps.append(("DELIVERED", "Pedido entregue.", "Loja", 60 * 24 * 4))
                if status == "CANCELED":
                    steps.append(("CANCELED", "Cancelado a pedido do cliente.", customer["name"], 60 * 3))
            history = [
                OrderStatusHistory(status=st, note=note, actor=actor, created_at=created + timedelta(minutes=minutes, seconds=1))
                for st, note, actor, minutes in steps
            ]
            order.updated_at = history[-1].created_at
            order.save(force_insert=True)
            for item in items:
                item.order = order
            for h in history:
                h.order = order
            OrderItem.objects.bulk_create(items)
            OrderStatusHistory.objects.bulk_create(history)
    return True
