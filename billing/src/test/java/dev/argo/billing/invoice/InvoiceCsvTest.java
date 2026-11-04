package dev.argo.billing.invoice;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class InvoiceCsvTest {

    @Test
    void formatsMoneyPercentAndDates() {
        assertThat(InvoiceCsv.money(0)).isEqualTo("0,00");
        assertThat(InvoiceCsv.money(123456)).isEqualTo("1234,56");
        assertThat(InvoiceCsv.percent(new BigDecimal("0.1645"))).isEqualTo("16,45");
        assertThat(InvoiceCsv.percent(new BigDecimal("0.1000"))).isEqualTo("10");
        assertThat(InvoiceCsv.when(Instant.parse("2026-11-04T15:30:00Z"))).isEqualTo("04/11/2026 12:30");
        assertThat(InvoiceCsv.when(null)).isEmpty();
    }

    @Test
    void quotesCellsThatNeedIt() {
        assertThat(InvoiceCsv.cell("Loja; Aurora")).isEqualTo("\"Loja; Aurora\"");
        assertThat(InvoiceCsv.cell("diz \"oi\"")).isEqualTo("\"diz \"\"oi\"\"\"");
        assertThat(InvoiceCsv.cell("simples")).isEqualTo("simples");
        assertThat(InvoiceCsv.cell(null)).isEmpty();
    }
}
