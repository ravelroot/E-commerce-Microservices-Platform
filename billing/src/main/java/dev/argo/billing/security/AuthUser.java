package dev.argo.billing.security;

public record AuthUser(String id, String role, String name) {

    public boolean isAdmin() {
        return "ADMIN".equals(role);
    }

    public boolean isSeller() {
        return "SELLER".equals(role);
    }
}
