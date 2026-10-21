package dev.argo.billing.invoice;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "invoice_items")
public class InvoiceItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "invoice_id")
    private Invoice invoice;

    @Column(name = "product_id", nullable = false, length = 36)
    private String productId;

    @Column(name = "seller_id", nullable = false, length = 36)
    private String sellerId;

    @Column(nullable = false, length = 140)
    private String description;

    @Column(nullable = false)
    private int quantity;

    @Column(name = "unit_price_cents", nullable = false)
    private long unitPriceCents;

    @Column(name = "total_cents", nullable = false)
    private long totalCents;

    protected InvoiceItem() {
    }

    public InvoiceItem(String productId, String sellerId, String description, int quantity, long unitPriceCents) {
        this.productId = productId;
        this.sellerId = sellerId;
        this.description = description;
        this.quantity = quantity;
        this.unitPriceCents = unitPriceCents;
        this.totalCents = unitPriceCents * quantity;
    }

    void attach(Invoice invoice) {
        this.invoice = invoice;
    }

    public String getProductId() { return productId; }
    public String getSellerId() { return sellerId; }
    public String getDescription() { return description; }
    public int getQuantity() { return quantity; }
    public long getUnitPriceCents() { return unitPriceCents; }
    public long getTotalCents() { return totalCents; }
}
