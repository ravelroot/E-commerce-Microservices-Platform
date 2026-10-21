package dev.argo.billing.invoice;

import dev.argo.billing.invoice.InvoiceDtos.InvoiceView;
import dev.argo.billing.invoice.InvoiceDtos.IssueRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/internal/invoices")
public class InternalInvoiceController {

    private final InvoiceService service;

    public InternalInvoiceController(InvoiceService service) {
        this.service = service;
    }

    @PostMapping
    public ResponseEntity<InvoiceView> issue(@Valid @RequestBody IssueRequest body) {
        var result = service.issue(body);
        return ResponseEntity.status(result.created() ? HttpStatus.CREATED : HttpStatus.OK)
                .body(InvoiceView.of(result.invoice()));
    }

    @PostMapping("/{orderId}/cancel")
    public InvoiceView cancel(@PathVariable Long orderId) {
        return InvoiceView.of(service.cancel(orderId));
    }
}
