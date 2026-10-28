package dev.argo.billing.invoice;

import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface InvoiceRepository extends JpaRepository<Invoice, Long> {

    @EntityGraph(attributePaths = "items")
    Optional<Invoice> findByOrderId(Long orderId);

    @EntityGraph(attributePaths = "items")
    Optional<Invoice> findByNumber(String number);

    Page<Invoice> findByCustomerId(String customerId, Pageable pageable);

    @Query("select i from Invoice i where exists (select 1 from InvoiceItem it where it.invoice = i and it.sellerId = :seller)")
    Page<Invoice> findBySeller(@Param("seller") String sellerId, Pageable pageable);

    @Query("""
            select count(i), coalesce(sum(i.totalCents), 0), coalesce(sum(i.taxCents), 0)
            from Invoice i where i.status = dev.argo.billing.invoice.InvoiceStatus.ISSUED
            and (:customer is null or i.customerId = :customer)
            and (:seller is null or exists (select 1 from InvoiceItem it where it.invoice = i and it.sellerId = :seller))
            """)
    Object[] totals(@Param("customer") String customerId, @Param("seller") String sellerId);

    @Query("""
            select count(i) from Invoice i where i.status = dev.argo.billing.invoice.InvoiceStatus.CANCELED
            and (:customer is null or i.customerId = :customer)
            and (:seller is null or exists (select 1 from InvoiceItem it where it.invoice = i and it.sellerId = :seller))
            """)
    long canceled(@Param("customer") String customerId, @Param("seller") String sellerId);

    /** Para o vendedor: só os itens dele nas notas emitidas, agrupados pela alíquota da nota. */
    @Query("""
            select it.invoice.taxRate, count(distinct it.invoice.id), coalesce(sum(it.totalCents), 0)
            from InvoiceItem it where it.sellerId = :seller
            and it.invoice.status = dev.argo.billing.invoice.InvoiceStatus.ISSUED
            group by it.invoice.taxRate
            """)
    java.util.List<Object[]> sellerTotals(@Param("seller") String sellerId);
}
