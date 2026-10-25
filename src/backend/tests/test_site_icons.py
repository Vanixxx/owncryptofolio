"""Website icons of exchanges (ADR: fetched by each installation itself)."""


def test_icon_links_never_reach_the_home_network_or_local_files(monkeypatch):
    """The links come from a third-party page (review 2026-10-24)."""
    import socket

    import pytest

    from app.modules.logos import site_icons

    def resolve(host, port, proto=0):
        ip = {"exchange.example": "93.184.216.34", "evil.example": "192.168.1.1"}.get(host, host)
        return [(socket.AF_INET, socket.SOCK_STREAM, proto, "", (ip, port))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    site_icons._public("https://exchange.example/favicon.ico")  # fine
    for url in (
        "file:///etc/passwd",
        "ftp://exchange.example/x.png",
        "http://evil.example/router.png",
        "http://127.0.0.1/x.png",
    ):
        with pytest.raises(ValueError):
            site_icons._public(url)
