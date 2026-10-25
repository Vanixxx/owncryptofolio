"""Own logos: only real images, kept in the database, served safely."""

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def test_upload_show_replace_and_remove(authed):
    r = authed.put("/api/logos/wallet/7", files={"file": ("tangem.png", PNG, "image/png")})
    assert r.status_code == 204
    assert [(x["kind"], x["key"]) for x in authed.get("/api/logos").json()] == [("wallet", "7")]
    shown = authed.get("/api/logos/wallet/7")
    assert shown.content == PNG and shown.headers["content-type"] == "image/png"
    authed.put("/api/logos/coin/ron", files={"file": ("r.svg", SVG, "image/svg+xml")})
    svg = authed.get("/api/logos/coin/RON")  # coins by symbol, any case
    assert "sandbox" in svg.headers["content-security-policy"]  # a script inside runs nothing
    assert authed.delete("/api/logos/wallet/7").status_code == 204
    assert authed.get("/api/logos/wallet/7").status_code == 404


def test_only_images_and_not_too_big(authed):
    fake = authed.put(
        "/api/logos/source/1", files={"file": ("x.png", b"hello, not an image", "image/png")}
    )
    assert fake.status_code == 400 and fake.json()["error"]["code"] == "logos.not_an_image"
    big = authed.put(
        "/api/logos/source/1", files={"file": ("x.png", PNG + b"\x00" * 600_000, "image/png")}
    )
    assert big.status_code == 400 and big.json()["error"]["code"] == "logos.too_large"
    assert (
        authed.put("/api/logos/user/1", files={"file": ("x.png", PNG, "image/png")}).status_code
        == 400
    )


def test_svg_from_drawing_programs_is_accepted():
    from app.modules.logos.service import sniff

    inkscape = (
        b'\xef\xbb\xbf<?xml version="1.0"?>\n<!-- Created with Inkscape -->\n<svg width="10"></svg>'
    )
    assert sniff(inkscape) == "image/svg+xml"
    assert sniff(b"<html><body>no</body></html>") is None


def test_site_icon_is_fetched_once_and_kept(authed, tmp_path, monkeypatch):
    # the project ships no third-party logo: each installation asks the exchange's website
    from app.modules.logos import site_icons

    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    asked = []

    def fake(url):
        asked.append(url)
        if url.endswith("/"):
            return b'<link rel="icon" sizes="32x32" href="/i32.png"><link rel="apple-touch-icon" href="/apple.png">'
        if url.endswith("/apple.png"):
            return png
        raise site_icons.urllib.error.URLError("no")

    monkeypatch.setattr(site_icons, "_get", fake)
    monkeypatch.setattr(
        site_icons, "website", lambda p: "https://ex.example/" if p == "xt" else None
    )
    r = authed.get("/api/logos/site/xt")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == png
    assert asked[1].endswith("/apple.png")  # the best icon first
    n = len(asked)
    assert authed.get("/api/logos/site/xt").status_code == 200 and len(asked) == n  # kept
    assert authed.get("/api/logos/site/unknown").status_code == 404


def test_site_icon_refuses_what_is_no_image(authed, monkeypatch):
    from app.modules.logos import site_icons

    monkeypatch.setattr(site_icons, "_get", lambda url: b"<html>not an image</html>")
    monkeypatch.setattr(site_icons, "website", lambda p: "https://ex.example/")
    assert authed.get("/api/logos/site/woo").status_code == 404
    assert authed.get("/api/logos/site/woo").status_code == 404  # marker: not asked again
