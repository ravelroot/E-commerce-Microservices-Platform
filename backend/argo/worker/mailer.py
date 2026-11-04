from __future__ import annotations

from html import escape
from typing import Protocol

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

STATUS_COPY = {
    "SHIPPED": ("Pedido {code} enviado", "Seu pedido {code} saiu para entrega.", "Acompanhar entrega"),
    "DELIVERED": ("Pedido {code} entregue", "Seu pedido {code} foi entregue. Obrigado pela compra!", "Ver pedido"),
}


class Mailer(Protocol):
    def send(self, to: str, subject: str, text: str, html: str) -> None: ...


class DjangoMailer:
    def send(self, to: str, subject: str, text: str, html: str) -> None:
        message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to])
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)


def money(cents: int) -> str:
    value = f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {value}"


def _layout(title: str, lead: str, body_html: str, link: str, label: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:#f6f7f7;font-family:Segoe UI,Arial,sans-serif;color:#15181b">
<div style="max-width:520px;margin:32px auto;background:#fff;border:1px solid #e2e5e6;border-radius:8px;padding:28px">
<p style="font-weight:700;font-size:18px;margin:0 0 20px">Argo</p>
<h1 style="font-size:20px;margin:0 0 8px">{escape(title)}</h1>
<p style="color:#5f666b;margin:0 0 20px">{lead}</p>
{body_html}
<a href="{escape(link)}" style="display:inline-block;margin-top:16px;background:#15181b;color:#fff;text-decoration:none;padding:10px 16px;border-radius:6px;font-weight:600">{escape(label)}</a>
</div></body></html>"""


def _items_table(order: dict) -> str:
    rows = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #e2e5e6">{i["quantity"]} × {escape(i["product_name"])}</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid #e2e5e6;text-align:right">{money(i["subtotal_cents"])}</td></tr>'
        for i in order["items"]
    )
    total = money(order["total_cents"])
    return (
        f'<table style="width:100%;border-collapse:collapse;font-size:14px">{rows}'
        f'<tr><td style="padding:12px 0;font-weight:700">Total</td>'
        f'<td style="padding:12px 0;text-align:right;font-weight:700">{total}</td></tr></table>'
    )


def confirmation_email(order: dict, public_url: str) -> tuple[str, str, str]:
    code = order["code"]
    first = order["customer_name"].split()[0]
    lines = [f"{i['quantity']} × {i['product_name']} — {money(i['subtotal_cents'])}" for i in order["items"]]
    link = f"{public_url}/#/pedidos/{order['id']}"
    subject = f"Pedido {code} confirmado"
    text = (
        f"Olá, {first}!\n\nSeu pedido {code} foi confirmado e o estoque já está reservado.\n\n"
        + "\n".join(lines)
        + f"\n\nTotal: {money(order['total_cents'])}\n\nAcompanhe em {link}\n\nArgo"
    )
    lead = f"Olá, {escape(first)}! O estoque já está reservado para você."
    html = _layout(f"Pedido {code} confirmado", lead, _items_table(order), link, "Acompanhar pedido")
    return subject, text, html


def _status_note(order: dict, status: str) -> str:
    notes = [h["note"] for h in order.get("history", []) if h["status"] == status and h.get("note")]
    return notes[-1] if notes else ""


def status_email(order: dict, public_url: str) -> tuple[str, str, str]:
    status = order["status"]
    subject_tpl, lead_tpl, label = STATUS_COPY[status]
    code = order["code"]
    first = order["customer_name"].split()[0]
    link = f"{public_url}/#/pedidos/{order['id']}"
    subject = subject_tpl.format(code=code)
    lead = lead_tpl.format(code=code)
    note = _status_note(order, status)
    text = f"Olá, {first}!\n\n{lead}\n" + (f"\n{note}\n" if note else "") + f"\nAcompanhe em {link}\n\nArgo"
    extra = (
        f'<p style="margin:0 0 8px;padding:12px 14px;background:#f6f7f7;border-radius:6px;font-size:14px">{escape(note)}</p>'
        if note
        else ""
    )
    html = _layout(subject, f"Olá, {escape(first)}! {escape(lead)}", extra + _items_table(order), link, label)
    return subject, text, html
