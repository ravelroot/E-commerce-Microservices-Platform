package dev.argo.billing;

import static org.assertj.core.api.Assertions.assertThat;

import dev.argo.billing.invoice.InvoiceService;
import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

class TaxTest {

    @Test
    void roundsHalfUpToTheCent() {
        BigDecimal rate = new BigDecimal("0.1645");
        assertThat(InvoiceService.tax(5000, rate)).isEqualTo(823);
        assertThat(InvoiceService.tax(0, rate)).isZero();
        assertThat(InvoiceService.tax(100, new BigDecimal("0.0050"))).isEqualTo(1);
        assertThat(InvoiceService.tax(99, new BigDecimal("0.0050"))).isZero();
    }
}
