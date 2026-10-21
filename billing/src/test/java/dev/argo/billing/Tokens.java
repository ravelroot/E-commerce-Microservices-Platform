package dev.argo.billing;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

final class Tokens {

    static final String SECRET = "segredo-de-teste-com-tamanho-suficiente-para-hs256";
    static final String ADMIN = "00000000-0000-0000-0000-00000000000a";
    static final String SELLER_A = "00000000-0000-0000-0000-0000000000a1";
    static final String SELLER_B = "00000000-0000-0000-0000-0000000000b1";
    static final String CUSTOMER = "00000000-0000-0000-0000-0000000000c1";
    static final String OTHER_CUSTOMER = "00000000-0000-0000-0000-0000000000c2";

    private Tokens() {
    }

    static String token(String sub, String role) {
        return build(sub, role, "access", "argo-identity", Instant.now().plusSeconds(600), SECRET, "HS256");
    }

    static String build(String sub, String role, String type, String iss, Instant exp, String secret, String alg) {
        String header = b64("{\"alg\":\"" + alg + "\",\"typ\":\"JWT\"}");
        String payload = b64("{\"iss\":\"" + iss + "\",\"sub\":\"" + sub + "\",\"role\":\"" + role
                + "\",\"name\":\"Teste\",\"type\":\"" + type + "\",\"iat\":" + Instant.now().getEpochSecond()
                + ",\"exp\":" + exp.getEpochSecond() + "}");
        String data = header + "." + payload;
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return data + "." + Base64.getUrlEncoder().withoutPadding().encodeToString(mac.doFinal(data.getBytes(StandardCharsets.US_ASCII)));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static String b64(String s) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(s.getBytes(StandardCharsets.UTF_8));
    }
}
