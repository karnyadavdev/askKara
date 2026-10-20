from starlette.requests import Request

from kara.deps import client_ip


def _request(headers: dict | None = None, client_host: str = "127.0.0.1") -> Request:
    scope = {
        "type": "http",
        "headers": [(key.encode(), value.encode()) for key, value in (headers or {}).items()],
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_client_ip_ignores_forwarded_header_by_default():
    request = _request({"x-forwarded-for": "9.9.9.9"})
    assert client_ip(request) == "127.0.0.1"


def test_client_ip_trusts_proxy_when_enabled():
    request = _request({"x-forwarded-for": "9.9.9.9, 10.0.0.1"})
    assert client_ip(request, trust_proxy=True) == "9.9.9.9"


def test_client_ip_falls_back_when_header_missing():
    request = _request()
    assert client_ip(request, trust_proxy=True) == "127.0.0.1"
