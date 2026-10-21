package dev.argo.billing.invoice;

import dev.argo.billing.invoice.InvoiceDtos.InvoiceSummary;
import dev.argo.billing.invoice.InvoiceDtos.InvoiceView;
import dev.argo.billing.invoice.InvoiceDtos.PageView;
import dev.argo.billing.invoice.InvoiceDtos.Totals;
import dev.argo.billing.security.AuthUser;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/invoices")
public class InvoiceController {

    private final InvoiceService service;

    public InvoiceController(InvoiceService service) {
        this.service = service;
    }

    @GetMapping
    public PageView<InvoiceSummary> list(@AuthenticationPrincipal AuthUser user,
            @RequestParam(defaultValue = "1") int page, @RequestParam(defaultValue = "20") int size) {
        var result = service.list(user, page, size);
        return new PageView<>(result.getContent().stream().map(InvoiceSummary::of).toList(),
                result.getNumber() + 1, result.getSize(), result.getTotalElements());
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
