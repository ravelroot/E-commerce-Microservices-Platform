package dev.argo.billing.invoice;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "invoices")
public class Invoice {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 30)
    private String number;

    @Column(name = "order_id", nullable = false, unique = true)
    private Long orderId;

    @Column(name = "order_code", nullable = false, length = 20)
    private String orderCode;

    @Column(name = "customer_id", nullable = false, length = 36)
    private String customerId;

    @Column(name = "customer_name", nullable = false, length = 120)
    private String customerName;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private InvoiceStatus status = InvoiceStatus.ISSUED;

    @Column(name = "total_cents", nullable = false)
    private long totalCents;

    @Column(name = "tax_cents", nullable = false)
    private long taxCents;

    @Column(name = "tax_rate", nullable = false, precision = 5, scale = 4)
    private BigDecimal taxRate;

    @Column(name = "issued_at", nullable = false)
    private Instant issuedAt;

    @Column(name = "canceled_at")
    private Instant canceledAt;

    @OneToMany(mappedBy = "invoice", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("id")
    private List<InvoiceItem> items = new ArrayList<>();

    protected Invoice() {
    }

    public Invoice(Long orderId, String orderCode, String customerId, String customerName, long totalCents,
            long taxCents, BigDecimal taxRate, Instant issuedAt) {
        this.orderId = orderId;
        this.orderCode = orderCode;
        this.customerId = customerId;
        this.customerName = customerName;
        this.totalCents = totalCents;
        this.taxCents = taxCents;
        this.taxRate = taxRate;
        this.issuedAt = issuedAt;
    }

    public void addItem(InvoiceItem item) {
        item.attach(this);
        items.add(item);
    }

    public void cancel(Instant when) {
        if (status == InvoiceStatus.ISSUED) {
            status = InvoiceStatus.CANCELED;
            canceledAt = when;
        }
    }

    public Long getId() { return id; }
    public String getNumber() { return number; }
    public void setNumber(String number) { this.number = number; }
    public Long getOrderId() { return orderId; }
    public String getOrderCode() { return orderCode; }
    public String getCustomerId() { return customerId; }
    public String getCustomerName() { return customerName; }
    public InvoiceStatus getStatus() { return status; }
    public long getTotalCents() { return totalCents; }
    public long getTaxCents() { return taxCents; }
    public BigDecimal getTaxRate() { return taxRate; }
    public Instant getIssuedAt() { return issuedAt; }
    public Instant getCanceledAt() { return canceledAt; }
    public List<InvoiceItem> getItems() { return items; }
}
