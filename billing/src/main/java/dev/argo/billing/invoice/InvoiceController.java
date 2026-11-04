package dev.argo.billing.invoice;

import dev.argo.billing.invoice.InvoiceDtos.Filters;
import dev.argo.billing.invoice.InvoiceDtos.InvoiceSummary;
import dev.argo.billing.invoice.InvoiceDtos.InvoiceView;
import dev.argo.billing.invoice.InvoiceDtos.PageView;
import dev.argo.billing.invoice.InvoiceDtos.Totals;
import dev.argo.billing.security.AuthUser;
import java.time.LocalDate;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.CacheControl;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/invoices")
public class InvoiceController {

    private static final MediaType CSV = MediaType.parseMediaType("text/csv; charset=UTF-8");

    private final InvoiceService service;

    public InvoiceController(InvoiceService service) {
        this.service = service;
    }

    @GetMapping
    public PageView<InvoiceSummary> list(@AuthenticationPrincipal AuthUser user,
            @RequestParam(defaultValue = "1") int page, @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String status, @RequestParam(required = false) String q,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
        var result = service.list(user, new Filters(status, q, from, to), page, size);
        return new PageView<>(result.getContent().stream().map(InvoiceSummary::of).toList(),
                result.getNumber() + 1, result.getSize(), result.getTotalElements());
    }

    @GetMapping("/export")
    public ResponseEntity<byte[]> export(@AuthenticationPrincipal AuthUser user,
            @RequestParam(required = false) String status, @RequestParam(required = false) String q,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
        byte[] body = InvoiceCsv.render(service.export(user, new Filters(status, q, from, to)));
        return ResponseEntity.ok()
                .contentType(CSV)
                .cacheControl(CacheControl.noStore())
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename("argo-notas.csv").build().toString())
                .body(body);
    }

    @GetMapping("/summary")
    public Totals summary(@AuthenticationPrincipal AuthUser user) {
        return service.totals(user);
    }

    @GetMapping("/{number}")
    public InvoiceView get(@AuthenticationPrincipal AuthUser user, @PathVariable String number) {
        return InvoiceView.of(service.get(user, number));
    }
}
