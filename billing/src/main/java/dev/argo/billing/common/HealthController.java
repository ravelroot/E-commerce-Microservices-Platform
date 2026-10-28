package dev.argo.billing.common;

import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {

    private final String version;

    public HealthController(@Value("${argo.version:dev}") String version) {
        this.version = version;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok", "service", "billing", "version", version);
    }
}
