package dev.argo.billing.invoice;

import dev.argo.billing.common.ApiException;
import dev.argo.billing.config.BillingProperties;
import dev.argo.billing.invoice.InvoiceDtos.IssueRequest;
import dev.argo.billing.invoice.InvoiceDtos.ItemInput;
import dev.argo.billing.security.AuthUser;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class InvoiceService {

    private static final ZoneId BRT = ZoneId.of("America/Sao_Paulo");

    private final InvoiceRepository invoices;
    private final BillingProperties props;
    private final Clock clock;
    private final TransactionTemplate tx;
    private final JdbcTemplate jdbc;

    public InvoiceService(InvoiceRepository invoices, BillingProperties props, Clock clock, TransactionTemplate tx,
            JdbcTemplate jdbc) {
        this.invoices = invoices;
        this.props = props;
        this.clock = clock;
        this.tx = tx;
        this.jdbc = jdbc;
    }

    public static long tax(long totalCents, BigDecimal rate) {
        return BigDecimal.valueOf(totalCents).multiply(rate).setScale(0, RoundingMode.HALF_UP).longValueExact();
    }

    public record Issued(Invoice invoice, boolean created) {
    }

    public Issued issue(IssueRequest req) {
        var existing = invoices.findByOrderId(req.orderId());
        if (existing.isPresent()) {
            return new Issued(existing.get(), false);
        }
        long itemsTotal = req.items().stream().mapToLong(i -> i.unitPriceCents() * i.quantity()).sum();
        if (itemsTotal != req.totalCents()) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "total_mismatch",
                    "A soma dos itens não confere com o total do pedido.");
        }
        try {
            Invoice created = tx.execute(status -> {
                Instant now = clock.instant();
                Long seq = jdbc.queryForObject("SELECT next_val FROM invoice_number_seq WHERE id = 1 FOR UPDATE", Long.class);
                jdbc.update("UPDATE invoice_number_seq SET next_val = next_val + 1 WHERE id = 1");
                Invoice inv = new Invoice(req.orderId(), req.orderCode(), req.customerId(), req.customerName(),
                        req.totalCents(), tax(req.totalCents(), props.taxRate()), props.taxRate(), now);
                for (ItemInput i : req.items()) {
                    inv.addItem(new InvoiceItem(i.productId(), i.sellerId(), i.description(), i.quantity(), i.unitPriceCents()));
                }
                inv.setNumber("%s-%d-%06d".formatted(props.invoicePrefix(), now.atZone(BRT).getYear(), seq));
                return invoices.saveAndFlush(inv);
            });
            return new Issued(created, true);
        } catch (DataIntegrityViolationException race) {
            return new Issued(invoices.findByOrderId(req.orderId()).orElseThrow(() -> race), false);
        }
    }

    @Transactional
    public Invoice cancel(Long orderId) {
        Invoice inv = invoices.findByOrderId(orderId).orElseThrow(() -> ApiException.notFound("Nota fiscal"));
        inv.cancel(clock.instant());
        return inv;
    }

    @Transactional(readOnly = true)
    public Page<Invoice> list(AuthUser user, int page, int size) {
        var pageable = PageRequest.of(Math.max(page, 1) - 1, Math.min(Math.max(size, 1), 100), Sort.by(Sort.Direction.DESC, "id"));
        if (user.isAdmin()) {
            return invoices.findAll(pageable);
        }
        if (user.isSeller()) {
            return invoices.findBySeller(user.id(), pageable);
        }
        return invoices.findByCustomerId(user.id(), pageable);
    }

    @Transactional(readOnly = true)
    public Invoice get(AuthUser user, String number) {
        Invoice inv = invoices.findByNumber(number).orElseThrow(() -> ApiException.notFound("Nota fiscal"));
        boolean allowed = user.isAdmin()
                || inv.getCustomerId().equals(user.id())
                || (user.isSeller() && inv.getItems().stream().anyMatch(i -> i.getSellerId().equals(user.id())));
        if (!allowed) {
            throw ApiException.notFound("Nota fiscal");
        }
        return inv;
    }

    @Transactional(readOnly = true)
    public InvoiceDtos.Totals totals(AuthUser user) {
        String customer = user.isAdmin() || user.isSeller() ? null : user.id();
        String seller = user.isSeller() ? user.id() : null;
        Object[] row = invoices.totals(customer, seller);
        Object[] values = row.length == 1 && row[0] instanceof Object[] nested ? nested : row;
        return new InvoiceDtos.Totals(
                ((Number) values[0]).longValue(),
                invoices.canceled(customer, seller),
                ((Number) values[1]).longValue(),
                ((Number) values[2]).longValue());
    }
}
