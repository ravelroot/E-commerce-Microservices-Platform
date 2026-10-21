import httpx

from .errors import ApiError


def service_client(base_url: str, internal_token: str, timeout: float = 5.0) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        timeout=timeout,
        headers={"X-Internal-Token": internal_token, "User-Agent": "argo-service"},
    )


def call(client: httpx.Client, method: str, url: str, service: str, **kwargs) -> httpx.Response:
    try:
        response = client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise ApiError(503, "service_unavailable", f"O serviço de {service} não respondeu. Tente de novo.") from exc
    if response.status_code >= 500:
        raise ApiError(503, "service_unavailable", f"O serviço de {service} está com problemas. Tente de novo.")
    return response
