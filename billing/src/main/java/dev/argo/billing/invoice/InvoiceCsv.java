package dev.argo.billing.invoice;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.List;

public final class InvoiceCsv {

    private static final DateTimeFormatter WHEN = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm").withZone(InvoiceService.BRT);
    private static final String HEADER = String.join(";", "Nota", "Pedido", "Cliente", "Situação", "Emissão", "Cancelamento",
            "Total (R$)", "Tributos (R$)", "Alíquota (%)");

    private InvoiceCsv() {
    }

    public static byte[] render(List<Invoice> invoices) {
        StringBuilder out = new StringBuilder("﻿").append(HEADER).append("\r\n");
        for (Invoice i : invoices) {
            out.append(String.join(";",
                    cell(i.getNumber()),
                    cell(i.getOrderCode()),
                    cell(i.getCustomerName()),
                    i.getStatus() == InvoiceStatus.ISSUED ? "Emitida" : "Cancelada",
                    when(i.getIssuedAt()),
                    when(i.getCanceledAt()),
                    money(i.getTotalCents()),
                    money(i.getTaxCents()),
                    percent(i.getTaxRate())))
                    .append("\r\n");
        }
        return out.toString().getBytes(StandardCharsets.UTF_8);
    }

    static String money(long cents) {
        return BigDecimal.valueOf(cents, 2).toPlainString().replace('.', ',');
    }

    static String percent(BigDecimal rate) {
        return rate == null ? "" : rate.movePointRight(2).stripTrailingZeros().toPlainString().replace('.', ',');
    }

    static String when(Instant instant) {
        return instant == null ? "" : WHEN.format(instant);
    }

    static String cell(String value) {
        if (value == null) {
            return "";
        }
        if (value.contains(";") || value.contains("\"") || value.contains("\n") || value.contains("\r")) {
            return "\"" + value.replace("\"", "\"\"") + "\"";
        }
        return value;
    }
}
