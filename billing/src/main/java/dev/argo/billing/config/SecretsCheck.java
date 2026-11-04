package dev.argo.billing.config;

import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

@Component
public class SecretsCheck {

    private static final Logger log = LoggerFactory.getLogger(SecretsCheck.class);
    private static final Set<String> EXAMPLES = Set.of(
            "troque-este-segredo-por-um-valor-longo-e-aleatorio",
            "troque-por-um-valor-aleatorio-com-pelo-menos-32-caracteres",
            "troque-este-token-interno",
            "troque-por-outro-valor-aleatorio");

    private final BillingProperties props;

    public SecretsCheck(BillingProperties props) {
        this.props = props;
    }

    public boolean weakJwtSecret() {
        String secret = props.jwtSecret();
        return secret == null || secret.length() < 32 || EXAMPLES.contains(secret);
    }

    public boolean weakInternalToken() {
        String token = props.internalToken();
        return token == null || token.length() < 24 || EXAMPLES.contains(token);
    }

    @EventListener(ApplicationReadyEvent.class)
    public void warn() {
        if (weakJwtSecret()) {
            log.warn("ARGO_JWT_SECRET é o valor de exemplo ou tem menos de 32 caracteres. Gere um valor aleatório longo.");
        }
        if (weakInternalToken()) {
            log.warn("ARGO_INTERNAL_TOKEN é o valor de exemplo ou tem menos de 24 caracteres. Gere um valor aleatório longo.");
        }
    }
}
