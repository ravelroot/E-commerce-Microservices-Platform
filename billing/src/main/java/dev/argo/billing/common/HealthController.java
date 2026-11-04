package dev.argo.billing.common;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {

    private final String version;
    private final String environment;
    private final JdbcTemplate jdbc;

    public HealthController(@Value("${argo.version:dev}") String version,
            @Value("${argo.environment:production}") String environment, JdbcTemplate jdbc) {
        this.version = version;
        this.environment = environment;
        this.jdbc = jdbc;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        long start = System.nanoTime();
        String database;
        try {
            jdbc.queryForObject("SELECT 1", Integer.class);
            database = "ok";
        } catch (RuntimeException e) {
            database = "erro: " + e.getClass().getSimpleName();
        }
        boolean healthy = "ok".equals(database);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("status", healthy ? "ok" : "degraded");
        body.put("service", "billing");
        body.put("version", version);
        body.put("environment", environment);
        body.put("checks", Map.of("database", database));
        body.put("duration_ms", Math.round((System.nanoTime() - start) / 100_000.0) / 10.0);
        return ResponseEntity.status(healthy ? 200 : 503).cacheControl(CacheControl.noStore()).body(body);
    }
}
