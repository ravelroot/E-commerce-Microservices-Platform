package dev.argo.billing.security;

import dev.argo.billing.config.BillingProperties;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.time.Clock;
import java.util.Base64;
import java.util.Set;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

@Component
public class JwtVerifier {

    private static final Set<String> ROLES = Set.of("ADMIN", "SELLER", "CUSTOMER");
    private static final Base64.Decoder B64 = Base64.getUrlDecoder();

    private final byte[] secret;
    private final String issuer;
    private final Clock clock;
    private final JsonMapper json = JsonMapper.builder().build();

    public JwtVerifier(BillingProperties props, Clock clock) {
        this.secret = props.jwtSecret().getBytes(StandardCharsets.UTF_8);
        this.issuer = props.jwtIssuer();
        this.clock = clock;
    }

    public AuthUser verify(String token) {
        String[] parts = token == null ? new String[0] : token.split("\\.");
        if (parts.length != 3) {
            throw new InvalidTokenException("formato");
        }
        try {
            JsonNode header = json.readTree(B64.decode(parts[0]));
            if (!"HS256".equals(header.path("alg").asString())) {
                throw new InvalidTokenException("algoritmo");
            }
            byte[] expected = sign(parts[0] + "." + parts[1]);
            if (!MessageDigest.isEqual(expected, B64.decode(parts[2]))) {
                throw new InvalidTokenException("assinatura");
            }
            JsonNode claims = json.readTree(B64.decode(parts[1]));
            if (!issuer.equals(claims.path("iss").asString())) {
                throw new InvalidTokenException("emissor");
            }
            if (!"access".equals(claims.path("type").asString())) {
                throw new InvalidTokenException("tipo");
            }
            if (claims.path("exp").asLong(0) <= clock.instant().getEpochSecond()) {
                throw new InvalidTokenException("expirado");
            }
            String role = claims.path("role").asString();
            String sub = claims.path("sub").asString();
            if (!ROLES.contains(role) || sub.isBlank()) {
                throw new InvalidTokenException("papel");
            }
            return new AuthUser(sub, role, claims.path("name").asString());
        } catch (IllegalArgumentException | tools.jackson.core.JacksonException e) {
            throw new InvalidTokenException("conteúdo");
        }
    }

    byte[] sign(String data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            return mac.doFinal(data.getBytes(StandardCharsets.US_ASCII));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    public static class InvalidTokenException extends RuntimeException {
        public InvalidTokenException(String reason) {
            super(reason);
        }
    }
}
