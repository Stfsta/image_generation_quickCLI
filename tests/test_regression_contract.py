from image_generator.api_client import ImageAPIClient
from image_generator.config import ConfigManager
from tests.conftest import FakeResponse


def test_generation_response_contract_url_or_b64_required(valid_api_key):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    result = client._parse_generation_response(FakeResponse(200, {"data": [{}]}))
    assert result.success is False
    assert "url 或 b64_json" in (result.error_message or "")


def test_config_backward_compat_legacy_base_url(make_config_file):
    path = make_config_file(
        {
            "api_base": "",
            "base_url": "https://api.suchuang.vip/v1/images/generations",
        }
    )
    cfg = ConfigManager(path).load()
    assert cfg.api_base == "https://api.suchuang.vip"


def test_endpoints_are_joined_from_api_base(valid_api_key):
    client = ImageAPIClient(api_key=valid_api_key, api_base="https://api.suchuang.vip")
    assert client._endpoint(client.GENERATIONS_PATH) == "https://api.suchuang.vip/v1/images/generations"
    assert client._endpoint(client.EDITS_PATH) == "https://api.suchuang.vip/v1/images/edits"
