package dev.argo.billing.common;

import java.util.Map;

public record ErrorBody(String code, String message, Map<String, String> fields) {

    public static ErrorBody of(String code, String message) {
        return new ErrorBody(code, message, Map.of());
    }
}
