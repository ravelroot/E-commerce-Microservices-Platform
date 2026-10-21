package dev.argo.billing;

import static dev.argo.billing.Tokens.ADMIN;
import static dev.argo.billing.Tokens.CUSTOMER;
import static dev.argo.billing.Tokens.OTHER_CUSTOMER;
import static dev.argo.billing.Tokens.SELLER_A;
import static dev.argo.billing.Tokens.SELLER_B;
import static dev.argo.billing.Tokens.token;
import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class BillingApiTest {

    static final String INTERNAL = "token-interno-de-teste";
    static final AtomicLong ORDERS = new AtomicLong(1000);

    @Value("${local.server.port}")
    int port;

    final HttpClient http = HttpClient.newHttpClient();
    final JsonMapper json = JsonMapper.builder().build();

    HttpResponse<String> call(String method, String path, String bearer, String internal, String body) throws Exception {
        HttpRequest.Builder b = HttpRequest.newBuilder(URI.create("http://localhost:" + port + "/api/billing" + path))
                .header("Content-Type", "application/json")
                .method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(body));
        if (bearer != null) {
            b.header("Authorization", "Bearer " + bearer);
        }
        if (internal != null) {
            b.header("X-Internal-Token", internal);
        }
        return http.send(b.build(), HttpResponse.BodyHandlers.ofString());
    }

    JsonNode read(HttpResponse<String> r) {
        return json.readTree(r.body());
    }

    String payload(long orderId, String customer, long total) {
        return """
                {"orderId": %d, "orderCode": "AR-%06d", "customerId": "%s", "customerName": "Cliente Teste",
                 "totalCents": %d, "items": [
                   {"productId": "p1", "sellerId": "%s", "description": "Café", "quantity": 2, "unitPriceCents": 1000},
                   {"productId": "p2", "sellerId": "%s", "description": "Caderno", "quantity": 1, "unitPriceCents": %d}
                 ]}
                """.formatted(orderId, orderId, customer, total, SELLER_A, SELLER_A, total - 2000);
    }

    JsonNode issue(long orderId, String customer) throws Exception {
        var r = call("POST", "/internal/invoices", null, INTERNAL, payload(orderId, customer, 5000));
        assertThat(r.statusCode()).isEqualTo(201);
        return read(r);
    }

    @Test
    void healthAndSpecArePublic() throws Exception {
        assertThat(read(call("GET", "/health", null, null, null)).path("status").asString()).isEqualTo("ok");
        var spec = call("GET", "/openapi.json", null, null, null);
        assertThat(spec.statusCode()).isEqualTo(200);
        assertThat(read(spec).path("openapi").asString()).startsWith("3.");
    }

    @Test
    void issuesInvoiceWithApproximateTaxesAndIsIdempotent() throws Exception {
        long order = ORDERS.incrementAndGet();
        JsonNode inv = issue(order, CUSTOMER);
        assertThat(inv.path("number").asString()).matches("NF-\\d{4}-\\d{6}");
        assertThat(inv.path("taxCents").asLong()).isEqualTo(823);
        assertThat(inv.path("items")).hasSize(2);
        assertThat(inv.path("status").asString()).isEqualTo("ISSUED");

        var again = call("POST", "/internal/invoices", null, INTERNAL, payload(order, CUSTOMER, 5000));
        assertThat(again.statusCode()).isEqualTo(200);
        assertThat(read(again).path("number").asString()).isEqualTo(inv.path("number").asString());
    }

    @Test
    void rejectsInvalidPayloads() throws Exception {
        var mismatch = call("POST", "/internal/invoices", null, INTERNAL, payload(ORDERS.incrementAndGet(), CUSTOMER, 5000)
                .replace("\"totalCents\": 5000", "\"totalCents\": 4999"));
        assertThat(mismatch.statusCode()).isEqualTo(422);
        assertThat(read(mismatch).path("code").asString()).isEqualTo("total_mismatch");

        var empty = call("POST", "/internal/invoices", null, INTERNAL,
                "{\"orderId\": 1, \"orderCode\": \"AR-1\", \"customerId\": \"c\", \"customerName\": \"\", \"totalCents\": 0, \"items\": []}");
        assertThat(empty.statusCode()).isEqualTo(422);
        assertThat(read(empty).path("fields").has("items")).isTrue();

        assertThat(call("POST", "/internal/invoices", null, INTERNAL, "{nao-e-json").statusCode()).isEqualTo(400);
    }

    @Test
    void internalRoutesNeedTheSharedSecret() throws Exception {
        String body = payload(ORDERS.incrementAndGet(), CUSTOMER, 5000);
        assertThat(call("POST", "/internal/invoices", null, null, body).statusCode()).isEqualTo(401);
        assertThat(call("POST", "/internal/invoices", null, "errado", body).statusCode()).isEqualTo(401);
        assertThat(call("POST", "/internal/invoices", token(ADMIN, "ADMIN"), null, body).statusCode()).isEqualTo(403);
    }

    @Test
    void cancelsInvoice() throws Exception {
        long order = ORDERS.incrementAndGet();
        issue(order, CUSTOMER);
        var r = call("POST", "/internal/invoices/" + order + "/cancel", null, INTERNAL, null);
        assertThat(read(r).path("status").asString()).isEqualTo("CANCELED");
        assertThat(read(r).path("canceledAt").isNull()).isFalse();
        assertThat(call("POST", "/internal/invoices/999999/cancel", null, INTERNAL, null).statusCode()).isEqualTo(404);
    }

    @Test
    void visibilityFollowsTheRole() throws Exception {
        String number = issue(ORDERS.incrementAndGet(), CUSTOMER).path("number").asString();

        assertThat(call("GET", "/invoices/" + number, token(CUSTOMER, "CUSTOMER"), null, null).statusCode()).isEqualTo(200);
        assertThat(call("GET", "/invoices/" + number, token(OTHER_CUSTOMER, "CUSTOMER"), null, null).statusCode()).isEqualTo(404);
        assertThat(call("GET", "/invoices/" + number, token(SELLER_A, "SELLER"), null, null).statusCode()).isEqualTo(200);
        assertThat(call("GET", "/invoices/" + number, token(SELLER_B, "SELLER"), null, null).statusCode()).isEqualTo(404);
        assertThat(call("GET", "/invoices/" + number, token(ADMIN, "ADMIN"), null, null).statusCode()).isEqualTo(200);

        JsonNode mine = read(call("GET", "/invoices", token(CUSTOMER, "CUSTOMER"), null, null));
        assertThat(mine.path("total").asLong()).isPositive();
        mine.path("items").forEach(i -> assertThat(i.path("customerName").asString()).isEqualTo("Cliente Teste"));
        assertThat(read(call("GET", "/invoices", token(SELLER_B, "SELLER"), null, null)).path("total").asLong()).isZero();
        assertThat(read(call("GET", "/invoices?page=1&size=2", token(ADMIN, "ADMIN"), null, null)).path("size").asInt()).isEqualTo(2);
    }

    @Test
    void summaryIsScoped() throws Exception {
        issue(ORDERS.incrementAndGet(), OTHER_CUSTOMER);
        JsonNode admin = read(call("GET", "/invoices/summary", token(ADMIN, "ADMIN"), null, null));
        JsonNode other = read(call("GET", "/invoices/summary", token(OTHER_CUSTOMER, "CUSTOMER"), null, null));
        JsonNode sellerB = read(call("GET", "/invoices/summary", token(SELLER_B, "SELLER"), null, null));
        assertThat(admin.path("issued").asLong()).isGreaterThanOrEqualTo(other.path("issued").asLong());
        assertThat(other.path("totalCents").asLong()).isEqualTo(5000L * other.path("issued").asLong());
        assertThat(sellerB.path("issued").asLong()).isZero();
    }

    @Test
    void rejectsBadTokens() throws Exception {
        assertThat(call("GET", "/invoices", null, null, null).statusCode()).isEqualTo(401);
        assertThat(call("GET", "/invoices", "abc", null, null).statusCode()).isEqualTo(401);
        String expired = Tokens.build(CUSTOMER, "CUSTOMER", "access", "argo-identity", Instant.now().minusSeconds(5), Tokens.SECRET, "HS256");
        String wrongSecret = Tokens.build(CUSTOMER, "CUSTOMER", "access", "argo-identity", Instant.now().plusSeconds(60), "outro-segredo", "HS256");
        String refresh = Tokens.build(CUSTOMER, "CUSTOMER", "refresh", "argo-identity", Instant.now().plusSeconds(60), Tokens.SECRET, "HS256");
        String issuer = Tokens.build(CUSTOMER, "CUSTOMER", "access", "outro", Instant.now().plusSeconds(60), Tokens.SECRET, "HS256");
        String none = Tokens.build(CUSTOMER, "CUSTOMER", "access", "argo-identity", Instant.now().plusSeconds(60), Tokens.SECRET, "none");
        String role = Tokens.build(CUSTOMER, "ROOT", "access", "argo-identity", Instant.now().plusSeconds(60), Tokens.SECRET, "HS256");
        for (String t : new String[] {expired, wrongSecret, refresh, issuer, none, role}) {
            assertThat(call("GET", "/invoices", t, null, null).statusCode()).isEqualTo(401);
        }
        assertThat(call("GET", "/nada", token(ADMIN, "ADMIN"), null, null).statusCode()).isEqualTo(403);
    }
}
