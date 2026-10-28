package dev.argo.billing.security;

import dev.argo.billing.config.BillingProperties;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http, JwtVerifier verifier, BillingProperties props) throws Exception {
        http.csrf(c -> c.disable())
                .httpBasic(b -> b.disable())
                .formLogin(f -> f.disable())
                .logout(l -> l.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(a -> a
                        .requestMatchers(HttpMethod.GET, "/health", "/openapi.json").permitAll()
                        .requestMatchers("/error").permitAll()
                        .requestMatchers("/internal/**").hasRole("INTERNAL")
                        .requestMatchers("/invoices/**", "/invoices").hasAnyRole("ADMIN", "SELLER", "CUSTOMER")
                        .anyRequest().denyAll())
                .exceptionHandling(e -> e
                        .authenticationEntryPoint((req, res, ex) -> write(res, 401, "unauthorized",
                                "Sessão inválida ou expirada. Entre novamente."))
                        .accessDeniedHandler((req, res, ex) -> write(res, 403, "forbidden",
                                "Você não tem permissão para esta ação.")))
                .addFilterBefore(new AuthFilter(verifier, props), UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }

    /** Sem usuários locais: evita a senha gerada no log; quem autentica é o JWT ou o token interno. */
    @Bean
    public UserDetailsService noLocalUsers() {
        return username -> {
            throw new UsernameNotFoundException(username);
        };
    }

    private static void write(HttpServletResponse res, int status, String code, String message) throws IOException {
        res.setStatus(status);
        res.setContentType("application/json");
        res.setCharacterEncoding(StandardCharsets.UTF_8.name());
        if (status == 401) {
            res.setHeader("WWW-Authenticate", "Bearer");
        }
        res.getWriter().write("{\"code\":\"" + code + "\",\"message\":\"" + message + "\",\"fields\":{}}");
    }
}
