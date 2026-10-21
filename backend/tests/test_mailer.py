import pytest

from argo.worker.mailer import DjangoMailer, confirmation_email, money


@pytest.mark.nodb
def test_money_format():
    assert money(0) == "R$ 0,00"
    assert money(123456789) == "R$ 1.234.567,89"


def test_confirmation_email_escapes_html(mailoutbox):
    order = {
        "id": 3,
        "code": "AR-000003",
        "customer_name": "Ana <script>",
        "total_cents": 1500,
        "items": [{"quantity": 1, "product_name": "Pão & <b>mel</b>", "subtotal_cents": 1500}],
    }
    subject, text, html = confirmation_email(order, "http://loja")
    assert subject == "Pedido AR-000003 confirmado"
    assert "http://loja/#/pedidos/3" in text and "R$ 15,00" in text
    assert "<script>" not in html and "&lt;b&gt;" in html
    DjangoMailer().send("a@argo.dev", subject, text, html)
    assert mailoutbox[0].to == ["a@argo.dev"]
    assert mailoutbox[0].from_email == "Argo <nao-responda@argo.dev>"
