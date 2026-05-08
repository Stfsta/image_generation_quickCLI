from pathlib import Path

from image_generator.api_client import DownloadResult, GenerationResult
from image_generator.config import ConfigManager
from image_generator.history import HistoryManager
from image_generator.image_service import ImageGenerationService


class FakeClient:
    MAX_EDIT_IMAGE_BYTES = 4 * 1024 * 1024

    def __init__(self, result: GenerationResult | None = None):
        self.calls = []
        self.result = result or GenerationResult(success=True, image_b64="aGVsbG8=")

    def generate(self, **kwargs):
        self.calls.append(("generate", kwargs))
        return self.result

    def edit(self, **kwargs):
        self.calls.append(("edit", kwargs))
        return self.result

    def save_b64(self, image_b64, image_dir, filename=None):
        self.calls.append(("save_b64", {"image_b64": image_b64, "image_dir": str(image_dir)}))
        return DownloadResult(success=True, filepath=str(Path(image_dir) / "b64.png"))

    def download(self, url, image_dir, filename=None):
        self.calls.append(("download", {"url": url, "image_dir": str(image_dir)}))
        return DownloadResult(success=True, filepath=str(Path(image_dir) / "url.png"))

    def close(self):
        return None


def _make_service(make_config_file, tmp_path, fake_client: FakeClient):
    config_path = make_config_file({"history_file": str(tmp_path / "hist.json")})
    cm = ConfigManager(config_path)
    hm = HistoryManager(tmp_path / "hist.json", max_history=10)
    return ImageGenerationService(config_manager=cm, history_manager=hm, api_client=fake_client)


def test_no_ref_uses_generate(make_config_file, tmp_path):
    client = FakeClient()
    svc = _make_service(make_config_file, tmp_path, client)
    svc.generate("hello")
    assert client.calls[0][0] == "generate"


def test_http_ref_uses_generate(make_config_file, tmp_path):
    client = FakeClient()
    svc = _make_service(make_config_file, tmp_path, client)
    svc.generate("hello", reference_image="https://example.com/ref.png")
    assert client.calls[0][0] == "generate"


def test_local_png_small_uses_edit(make_config_file, tmp_path, png_file):
    client = FakeClient()
    svc = _make_service(make_config_file, tmp_path, client)
    svc.generate("hello", reference_image=str(png_file))
    assert client.calls[0][0] == "edit"


def test_local_non_png_falls_back_generate(make_config_file, tmp_path, jpg_file):
    client = FakeClient()
    svc = _make_service(make_config_file, tmp_path, client)
    svc.generate("hello", reference_image=str(jpg_file))
    assert client.calls[0][0] == "generate"


def test_local_png_over_4mb_falls_back_generate(make_config_file, tmp_path):
    big_png = tmp_path / "big.png"
    big_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"a" * (4 * 1024 * 1024 + 1))
    client = FakeClient()
    svc = _make_service(make_config_file, tmp_path, client)
    svc.generate("hello", reference_image=str(big_png))
    assert client.calls[0][0] == "generate"


def test_service_prefers_b64_save_over_download(make_config_file, tmp_path):
    client = FakeClient(result=GenerationResult(success=True, image_b64="aGVsbG8=", image_url="https://x/y.png"))
    svc = _make_service(make_config_file, tmp_path, client)
    svc.generate("hello")
    call_names = [name for name, _ in client.calls]
    assert "save_b64" in call_names
    assert "download" not in call_names


def test_service_uses_download_when_only_url(make_config_file, tmp_path):
    client = FakeClient(result=GenerationResult(success=True, image_url="https://x/y.png"))
    svc = _make_service(make_config_file, tmp_path, client)
    svc.generate("hello")
    call_names = [name for name, _ in client.calls]
    assert "download" in call_names


def test_service_passes_size_priority(make_config_file, tmp_path):
    config_path = make_config_file({"default_size": "512x512", "history_file": str(tmp_path / "hist.json")})
    cm = ConfigManager(config_path)
    hm = HistoryManager(tmp_path / "hist.json", max_history=10)
    client = FakeClient()
    svc = ImageGenerationService(config_manager=cm, history_manager=hm, api_client=client)

    svc.generate("[size:1536x1024] hello")
    size_from_prompt = client.calls[0][1]["size"]
    assert size_from_prompt == "1536x1024"

    client.calls.clear()
    svc.generate("[size:1536x1024] hello", size="1792x1024")
    size_from_arg = client.calls[0][1]["size"]
    assert size_from_arg == "1792x1024"

    client.calls.clear()
    svc.generate("hello")
    size_from_default = client.calls[0][1]["size"]
    assert size_from_default == "512x512"
