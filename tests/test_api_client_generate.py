from tests.conftest import FakeResponse
from image_generator.api_client import ImageAPIClient


def test_generate_parses_url_response(valid_api_key, monkeypatch):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    monkeypatch.setattr(
        client._session,
        "post",
        lambda *args, **kwargs: FakeResponse(200, {"data": [{"url": "https://x/y.png"}]}),
    )
    result = client.generate("hello")
    assert result.success is True
    assert result.image_url == "https://x/y.png"


def test_generate_parses_b64_response(valid_api_key, monkeypatch):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    monkeypatch.setattr(
        client._session,
        "post",
        lambda *args, **kwargs: FakeResponse(200, {"data": [{"b64_json": "aGVsbG8="}]}),
    )
    result = client.generate("hello")
    assert result.success is True
    assert result.image_b64 == "aGVsbG8="


def test_generate_handles_missing_url_and_b64(valid_api_key, monkeypatch):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    monkeypatch.setattr(
        client._session,
        "post",
        lambda *args, **kwargs: FakeResponse(200, {"data": [{}]}),
    )
    result = client.generate("hello")
    assert result.success is False
    assert "url and b64_json" in (result.error_message or "")


def test_generate_uses_json_content_type(valid_api_key, monkeypatch):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    seen = {}

    def fake_post(*args, **kwargs):
        seen["headers"] = kwargs.get("headers")
        return FakeResponse(200, {"data": [{"url": "https://x/y.png"}]})

    monkeypatch.setattr(client._session, "post", fake_post)
    client.generate("hello")
    assert seen["headers"]["Content-Type"] == "application/json"


def test_generate_with_reference_url_uses_image_url_field(valid_api_key, monkeypatch):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    seen = {}

    def fake_post(*args, **kwargs):
        seen["json"] = kwargs.get("json")
        return FakeResponse(200, {"data": [{"url": "https://x/y.png"}]})

    monkeypatch.setattr(client._session, "post", fake_post)
    client.generate("hello", reference_image="https://example.com/ref.png")
    assert seen["json"]["image_url"] == "https://example.com/ref.png"


def test_generate_with_local_ref_encodes_data_uri(valid_api_key, monkeypatch, png_file, jpg_file, webp_file):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")

    seen_png = {}
    def fake_post_png(*args, **kwargs):
        seen_png["json"] = kwargs.get("json")
        return FakeResponse(200, {"data": [{"url": "https://x/y.png"}]})

    monkeypatch.setattr(client._session, "post", fake_post_png)
    client.generate("hello", reference_image=str(png_file))
    assert str(seen_png["json"]["image_url"]).startswith("data:image/png;base64,")

    def fake_post_jpg(*args, **kwargs):
        return FakeResponse(200, {"data": [{"url": "https://x/y.png"}]})

    monkeypatch.setattr(client._session, "post", fake_post_jpg)
    result_jpg = client.generate("hello", reference_image=str(jpg_file))
    assert result_jpg.success is True

    monkeypatch.setattr(client._session, "post", fake_post_jpg)
    result_webp = client.generate("hello", reference_image=str(webp_file))
    assert result_webp.success is True


def test_generate_with_multiple_references_uses_list_payload(valid_api_key, monkeypatch, png_file):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    seen = {}

    def fake_post(*args, **kwargs):
        seen["json"] = kwargs.get("json")
        return FakeResponse(200, {"data": [{"url": "https://x/y.png"}]})

    monkeypatch.setattr(client._session, "post", fake_post)
    client.generate("hello", reference_image=[str(png_file), "https://example.com/ref.png"])
    assert isinstance(seen["json"]["image_url"], list)
    assert len(seen["json"]["image_url"]) == 2


def test_generate_retries_429_then_success(valid_api_key, monkeypatch):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip", max_retries=3, retry_delay=0.0)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return FakeResponse(429, {}, "rate limited")
        return FakeResponse(200, {"data": [{"url": "https://x/y.png"}]})

    monkeypatch.setattr(client._session, "post", fake_post)
    result = client.generate("hello")
    assert result.success is True
    assert calls["count"] == 3
