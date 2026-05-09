from tests.conftest import FakeResponse
from image_generator.api_client import ImageAPIClient


def test_edit_rejects_non_png(valid_api_key, jpg_file):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    result = client.edit(prompt="edit", image_path=str(jpg_file))
    assert result.success is False
    assert "must be PNG" in (result.error_message or "")


def test_edit_rejects_file_over_4mb(valid_api_key, tmp_path):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    big_png = tmp_path / "big.png"
    big_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"a" * (4 * 1024 * 1024 + 1))
    result = client.edit(prompt="edit", image_path=str(big_png))
    assert result.success is False
    assert "too large" in (result.error_message or "")


def test_edit_builds_multipart_without_json_content_type(valid_api_key, monkeypatch, png_file):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    seen = {}

    def fake_post(*args, **kwargs):
        seen["files"] = kwargs.get("files")
        seen["headers"] = kwargs.get("headers")
        return FakeResponse(200, {"data": [{"b64_json": "aGVsbG8="}]})

    monkeypatch.setattr(client._session, "post", fake_post)
    result = client.edit(prompt="edit", image_path=str(png_file))
    assert result.success is True
    keys = [item[0] for item in (seen["files"] or [])]
    assert "image" in keys
    assert seen["headers"] is None


def test_edit_with_mask_includes_mask_part(valid_api_key, monkeypatch, png_file, tmp_path):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"\x89PNG\r\n\x1a\nmask")
    seen = {}

    def fake_post(*args, **kwargs):
        seen["files"] = kwargs.get("files")
        return FakeResponse(200, {"data": [{"b64_json": "aGVsbG8="}]})

    monkeypatch.setattr(client._session, "post", fake_post)
    result = client.edit(prompt="edit", image_path=str(png_file), mask_path=str(mask))
    assert result.success is True
    keys = [item[0] for item in (seen["files"] or [])]
    assert "mask" in keys


def test_edit_multiple_images_uses_image_list_parts(valid_api_key, monkeypatch, png_file, tmp_path):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    second = tmp_path / "second.png"
    second.write_bytes(b"\x89PNG\r\n\x1a\nsecond")
    seen = {}

    def fake_post(*args, **kwargs):
        seen["files"] = kwargs.get("files")
        return FakeResponse(200, {"data": [{"b64_json": "aGVsbG8="}]})

    monkeypatch.setattr(client._session, "post", fake_post)
    result = client.edit(prompt="edit", image_path=[str(png_file), str(second)])
    assert result.success is True
    keys = [item[0] for item in (seen["files"] or [])]
    assert keys.count("image") == 1
    assert keys.count("image[]") == 1


def test_edit_parses_b64_response(valid_api_key, monkeypatch, png_file):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    monkeypatch.setattr(
        client._session,
        "post",
        lambda *args, **kwargs: FakeResponse(200, {"data": [{"b64_json": "aGVsbG8="}]}),
    )
    result = client.edit(prompt="edit", image_path=str(png_file))
    assert result.success is True
    assert result.image_b64 == "aGVsbG8="


def test_edit_retries_on_429(valid_api_key, monkeypatch, png_file):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip", max_retries=3, retry_delay=0.0)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return FakeResponse(429, {}, "rate limited")
        return FakeResponse(200, {"data": [{"b64_json": "aGVsbG8="}]})

    monkeypatch.setattr(client._session, "post", fake_post)
    result = client.edit(prompt="edit", image_path=str(png_file))
    assert result.success is True
    assert calls["count"] == 3
