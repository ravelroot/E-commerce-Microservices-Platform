package dev.argo.billing.config;

import java.math.BigDecimal;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "argo")
public record BillingProperties(
        String jwtSecret,
        String jwtIssuer,
        String internalToken,
        BigDecimal taxRate,
        String invoicePrefix) {
}
