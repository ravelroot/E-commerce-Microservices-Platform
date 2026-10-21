package dev.argo.billing.security;

import dev.argo.billing.config.BillingProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

public class AuthFilter extends OncePerRequestFilter {

    private final JwtVerifier verifier;
    private final byte[] internalToken;

    public AuthFilter(JwtVerifier verifier, BillingProperties props) {
        this.verifier = verifier;
        this.internalToken = props.internalToken().getBytes(StandardCharsets.UTF_8);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        String internal = req.getHeader("X-Internal-Token");
        String auth = req.getHeader("Authorization");
        if (internal != null && MessageDigest.isEqual(internal.getBytes(StandardCharsets.UTF_8), internalToken)) {
            authenticate("service", "INTERNAL");
        } else if (auth != null && auth.regionMatches(true, 0, "Bearer ", 0, 7)) {
            try {
                AuthUser user = verifier.verify(auth.substring(7).trim());
                var token = new UsernamePasswordAuthenticationToken(user, null,
                        List.of(new SimpleGrantedAuthority("ROLE_" + user.role())));
                SecurityContextHolder.getContext().setAuthentication(token);
            } catch (JwtVerifier.InvalidTokenException e) {
                SecurityContextHolder.clearContext();
            }
        }
        chain.doFilter(req, res);
    }

    private static void authenticate(String name, String role) {
        var token = new UsernamePasswordAuthenticationToken(name, null, List.of(new SimpleGrantedAuthority("ROLE_" + role)));
        SecurityContextHolder.getContext().setAuthentication(token);
    }
}
