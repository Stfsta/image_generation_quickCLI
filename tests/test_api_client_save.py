from pathlib import Path

from image_generator.api_client import ImageAPIClient


def test_save_b64_writes_file(valid_api_key, tmp_path):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    result = client.save_b64("aGVsbG8=", tmp_path)
    assert result.success is True
    out = Path(result.filepath)
    assert out.exists()
    assert out.read_bytes()


def test_save_b64_accepts_data_uri(valid_api_key, tmp_path):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    result = client.save_b64("data:image/png;base64,aGVsbG8=", tmp_path)
    assert result.success is True
    assert Path(result.filepath).exists()


def test_save_b64_invalid_payload_fails(valid_api_key, tmp_path):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    result = client.save_b64("not-a-valid-base64%%%", tmp_path)
    assert result.success is False
    assert "解码失败" in (result.error_message or "")
