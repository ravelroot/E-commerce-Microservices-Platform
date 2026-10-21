"""E-mail de confirmação do pedido, enviado com django.core.mail (SMTP configurado por ARGO_SMTP_*)."""

from __future__ import annotations

from html import escape
from typing import Protocol

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


class Mailer(Protocol):
    def send(self, to: str, subject: str, text: str, html: str) -> None: ...


class DjangoMailer:
    """Usa o EMAIL_BACKEND do Django: SMTP em produção, memória (mail.outbox) nos testes."""

    def send(self, to: str, subject: str, text: str, html: str) -> None:
        message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to])
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)


def money(cents: int) -> str:
    value = f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {value}"


def confirmation_email(order: dict, public_url: str) -> tuple[str, str, str]:
    code = order["code"]
    first = order["customer_name"].split()[0]
    lines = [f"{i['quantity']} × {i['product_name']} — {money(i['subtotal_cents'])}" for i in order["items"]]
    subject = f"Pedido {code} confirmado"
    text = (
        f"Olá, {first}!\n\nSeu pedido {code} foi confirmado e o estoque já está reservado.\n\n"
        + "\n".join(lines)
        + f"\n\nTotal: {money(order['total_cents'])}\n\nAcompanhe em {public_url}/#/pedidos/{order['id']}\n\nArgo"
    )
    rows = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #e2e5e6">{i["quantity"]} × {escape(i["product_name"])}</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid #e2e5e6;text-align:right">{money(i["subtotal_cents"])}</td></tr>'
        for i in order["items"]
    )
    html = f"""<!doctype html><html><body style="margin:0;background:#f6f7f7;font-family:Segoe UI,Arial,sans-serif;color:#15181b">
<div style="max-width:520px;margin:32px auto;background:#fff;border:1px solid #e2e5e6;border-radius:8px;padding:28px">
<p style="font-weight:700;font-size:18px;margin:0 0 20px">Argo</p>
<h1 style="font-size:20px;margin:0 0 8px">Pedido {code} confirmado</h1>
<p style="color:#5f666b;margin:0 0 20px">Olá, {escape(first)}! O estoque já está reservado para você.</p>
<table style="width:100%;border-collapse:collapse;font-size:14px">{rows}
<tr><td style="padding:12px 0;font-weight:700">Total</td><td style="padding:12px 0;text-align:right;font-weight:700">{money(order["total_cents"])}</td></tr></table>
<a href="{public_url}/#/pedidos/{order["id"]}" style="display:inline-block;margin-top:16px;background:#15181b;color:#fff;text-decoration:none;padding:10px 16px;border-radius:6px;font-weight:600">Acompanhar pedido</a>
</div></body></html>"""
    return subject, text, html
