package dev.argo.billing.invoice;

import java.time.Instant;
import java.util.List;
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

    @Query(value = """
            select i from Invoice i
            where (:status is null or i.status = :status)
            and (:customer is null or i.customerId = :customer)
            and (:seller is null or exists (select 1 from InvoiceItem it where it.invoice = i and it.sellerId = :seller))
            and (:term is null or lower(i.number) like :term or lower(i.orderCode) like :term or lower(i.customerName) like :term)
            and (:issuedFrom is null or i.issuedAt >= :issuedFrom)
            and (:issuedTo is null or i.issuedAt < :issuedTo)
            """, countQuery = """
            select count(i) from Invoice i
            where (:status is null or i.status = :status)
            and (:customer is null or i.customerId = :customer)
            and (:seller is null or exists (select 1 from InvoiceItem it where it.invoice = i and it.sellerId = :seller))
            and (:term is null or lower(i.number) like :term or lower(i.orderCode) like :term or lower(i.customerName) like :term)
            and (:issuedFrom is null or i.issuedAt >= :issuedFrom)
            and (:issuedTo is null or i.issuedAt < :issuedTo)
            """)
    Page<Invoice> search(@Param("status") InvoiceStatus status, @Param("customer") String customerId,
            @Param("seller") String sellerId, @Param("term") String term, @Param("issuedFrom") Instant issuedFrom,
            @Param("issuedTo") Instant issuedTo, Pageable pageable);

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

    @Query("""
            select it.invoice.taxRate, count(distinct it.invoice.id), coalesce(sum(it.totalCents), 0)
            from InvoiceItem it where it.sellerId = :seller
            and it.invoice.status = dev.argo.billing.invoice.InvoiceStatus.ISSUED
            group by it.invoice.taxRate
            """)
    List<Object[]> sellerTotals(@Param("seller") String sellerId);
}
