import pytest

from image_generator.config import ConfigManager, ConfigValidationError


def test_load_legacy_base_url_derives_api_base(make_config_file):
    path = make_config_file(
        {
            "api_base": "",
            "base_url": "https://api.suchuang.vip/v1/images/generations",
        }
    )
    cfg = ConfigManager(path).load()
    assert cfg.api_base == "https://api.suchuang.vip"


def test_api_base_takes_precedence_over_base_url(make_config_file):
    path = make_config_file(
        {
            "api_base": "https://custom.example.com",
            "base_url": "https://api.suchuang.vip/v1/images/generations",
        }
    )
    cfg = ConfigManager(path).load()
    assert cfg.api_base == "https://custom.example.com"


@pytest.mark.parametrize(
    "size",
    [
        "256x256",
        "512x512",
        "1024x1024",
        "1536x1024",
        "1024x1536",
        "1792x1024",
        "1024x1792",
        "auto",
    ],
)
def test_default_size_accepts_full_union(make_config_file, size):
    path = make_config_file({"default_size": size})
    cfg = ConfigManager(path).load()
    assert cfg.default_size == size


def test_default_size_rejects_invalid_value(make_config_file):
    path = make_config_file({"default_size": "9999x9999"})
    with pytest.raises(ConfigValidationError):
        ConfigManager(path).load()


def test_language_accepts_en_and_zh(make_config_file):
    assert ConfigManager(make_config_file({"language": "en"})).load().language == "en"
    assert ConfigManager(make_config_file({"language": "zh"})).load().language == "zh"


def test_language_rejects_invalid_value(make_config_file):
    path = make_config_file({"language": "jp"})
    with pytest.raises(ConfigValidationError):
        ConfigManager(path).load()


def test_save_updates_persists_language(make_config_file):
    path = make_config_file({"language": "en"})
    manager = ConfigManager(path)
    manager.load()
    updated = manager.save_updates(language="zh")
    reloaded = ConfigManager(path).load()
    assert updated.language == "zh"
    assert reloaded.language == "zh"


def test_multi_ref_mode_accepts_supported_values(make_config_file):
    for mode in ("off", "direct", "collage"):
        cfg = ConfigManager(make_config_file({"multi_ref_mode": mode})).load()
        assert cfg.multi_ref_mode == mode


def test_multi_ref_mode_rejects_invalid_value(make_config_file):
    with pytest.raises(ConfigValidationError):
        ConfigManager(make_config_file({"multi_ref_mode": "unknown"})).load()
