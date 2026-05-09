import json
from pathlib import Path

import pytest


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def valid_api_key() -> str:
    return "sk-12345678901234567890"


@pytest.fixture
def make_config_file(tmp_path):
    def _make_config_file(overrides=None):
        cfg = {
            "api_key": "sk-12345678901234567890",
            "api_base": "https://api.suchuang.vip",
            "base_url": "https://api.suchuang.vip/v1/images/generations",
            "model": "gpt-image-2",
            "image_dir": str(tmp_path / "generated_images"),
            "reference_dir": str(tmp_path / "reference_images"),
            "history_file": str(tmp_path / "chat_memory.json"),
            "max_history": 10,
            "timeout": 90,
            "max_retries": 3,
            "retry_delay": 1.0,
            "default_size": "1024x1024",
            "language": "en",
        }
        if overrides:
            cfg.update(overrides)
        path = tmp_path / "config.json"
        path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        return path

    return _make_config_file


@pytest.fixture
def png_file(tmp_path):
    path = tmp_path / "ref.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\npng-bytes")
    return path


@pytest.fixture
def jpg_file(tmp_path):
    path = tmp_path / "ref.jpg"
    path.write_bytes(b"\xff\xd8\xffjpg-bytes")
    return path


@pytest.fixture
def webp_file(tmp_path):
    path = tmp_path / "ref.webp"
    path.write_bytes(b"RIFF0000WEBPwebp-bytes")
    return path
