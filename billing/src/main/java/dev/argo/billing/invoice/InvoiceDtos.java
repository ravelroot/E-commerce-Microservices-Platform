package dev.argo.billing.invoice;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public final class InvoiceDtos {

    private InvoiceDtos() {
    }

    public record IssueRequest(
            @NotNull @Positive Long orderId,
            @NotBlank @Size(max = 20) String orderCode,
            @NotBlank @Size(max = 36) String customerId,
            @NotBlank @Size(max = 120) String customerName,
            @NotNull @PositiveOrZero Long totalCents,
            @NotEmpty @Size(max = 100) List<@Valid ItemInput> items) {
    }

    public record ItemInput(
            @NotBlank @Size(max = 36) String productId,
            @NotBlank @Size(max = 36) String sellerId,
            @NotBlank @Size(max = 140) String description,
            @Positive @Max(10_000) int quantity,
            @PositiveOrZero long unitPriceCents) {
    }

    public record ItemView(String productId, String sellerId, String description, int quantity, long unitPriceCents,
            long totalCents) {
        static ItemView of(InvoiceItem i) {
            return new ItemView(i.getProductId(), i.getSellerId(), i.getDescription(), i.getQuantity(),
                    i.getUnitPriceCents(), i.getTotalCents());
        }
    }

    public record InvoiceSummary(String number, Long orderId, String orderCode, String customerName, String status,
            long totalCents, long taxCents, Instant issuedAt, Instant canceledAt) {
        static InvoiceSummary of(Invoice i) {
            return new InvoiceSummary(i.getNumber(), i.getOrderId(), i.getOrderCode(), i.getCustomerName(),
                    i.getStatus().name(), i.getTotalCents(), i.getTaxCents(), i.getIssuedAt(), i.getCanceledAt());
        }
    }

    public record InvoiceView(String number, Long orderId, String orderCode, String customerId, String customerName,
            String status, long totalCents, long taxCents, BigDecimal taxRate, Instant issuedAt, Instant canceledAt,
            List<ItemView> items) {
        static InvoiceView of(Invoice i) {
            return new InvoiceView(i.getNumber(), i.getOrderId(), i.getOrderCode(), i.getCustomerId(),
                    i.getCustomerName(), i.getStatus().name(), i.getTotalCents(), i.getTaxCents(), i.getTaxRate(),
                    i.getIssuedAt(), i.getCanceledAt(), i.getItems().stream().map(ItemView::of).toList());
        }
    }

    public record PageView<T>(List<T> items, int page, int size, long total) {
    }

    public record Totals(long issued, long canceled, long totalCents, long taxCents) {
    }
}
