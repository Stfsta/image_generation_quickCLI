"""
Configuration management with validation and schema enforcement.
配置管理模块，支持验证和模式强制。
"""

import json
import sys
from pathlib import Path
from typing import Any
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ConfigSchema:
    """Immutable configuration schema with type-safe defaults.
    不可变的配置模式，带有类型安全的默认值。"""
    api_key: str
    api_base: str = "https://api.suchuang.vip"
    base_url: str = "https://api.suchuang.vip/v1/images/generations"
    model: str = "gpt-image-2"
    image_dir: str = "./generated_images"
    history_file: str = "chat_memory.json"
    max_history: int = 10
    timeout: int = 90
    max_retries: int = 3
    retry_delay: float = 1.0
    default_size: str = "1024x1024"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails.
    配置验证失败时抛出的异常。"""
    pass


class ConfigManager:
    """
    Manages application configuration with validation, template generation,
    and secure handling of sensitive values.
    管理应用程序配置，支持验证、模板生成和敏感值的安全处理。
    """

    CONFIG_FILE = Path("config.json")
    ALLOWED_SIZES = {
        "256x256",
        "512x512",
        "1024x1024",
        "1536x1024",
        "1024x1536",
        "1792x1024",
        "1024x1792",
        "auto",
    }
    _TEMPLATE = {
        "api_key": "sk-在此填写您的速创API密钥",
        "api_base": "https://api.suchuang.vip",
        "base_url": "https://api.suchuang.vip/v1/images/generations",
        "model": "gpt-image-2",
        "image_dir": "./generated_images",
        "history_file": "chat_memory.json",
        "max_history": 10,
        "timeout": 90,
        "max_retries": 3,
        "retry_delay": 1.0,
        "default_size": "1024x1024"
    }

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._config_path = Path(config_path) if config_path else self.CONFIG_FILE
        self._config: ConfigSchema | None = None

    def _create_template(self) -> None:
        """Generate a template configuration file and exit gracefully.
        生成模板配置文件并优雅退出。"""
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._TEMPLATE, f, ensure_ascii=False, indent=2)
        print("[INFO] 已生成配置文件 config.json。")
        print("[INFO] Please open it with a text editor and enter your Suchuang API key.")
        print("       请用文本编辑器打开并填入您的速创API密钥。")
        print("       Get your key: https://api.suchuang.vip (Console -> API Keys)")
        print("       密钥获取地址: https://api.suchuang.vip (控制台 -> API 密钥)")
        sys.exit(0)

    def _derive_api_base(self, data: dict[str, Any]) -> str:
        """Derive API host from api_base or legacy base_url.
        从 api_base 或旧 base_url 派生 API host。"""
        api_base = str(data.get("api_base", "")).strip()
        legacy_base_url = str(data.get("base_url", "")).strip()

        candidate = api_base or legacy_base_url or self._TEMPLATE["api_base"]
        candidate = candidate.rstrip("/")
        if "/v1/images/" in candidate:
            print("[Info/信息] Detected legacy endpoint style base_url; deriving api_base automatically.")
            print("[Info/信息] 检测到旧版完整端点 base_url，已自动派生 api_base。")
            candidate = candidate.split("/v1/images/", 1)[0]
        return candidate.rstrip("/")

    def _validate(self, data: dict[str, Any]) -> ConfigSchema:
        """Validate raw configuration data against the schema.
        根据模式验证原始配置数据。"""
        required = ["api_key", "model"]
        missing = [key for key in required if key not in data or not data[key]]
        if missing:
            raise ConfigValidationError(
                f"Missing required config field(s): {', '.join(missing)}\n"
                f"配置文件中缺少必要字段: {', '.join(missing)}"
            )

        api_key = str(data.get("api_key", ""))
        model = str(data.get("model", "")).strip()
        if not model:
            raise ConfigValidationError("Missing required config field: model / 配置文件缺少必要字段: model")

        if api_key.startswith("sk-在此填写") or len(api_key) < 20:
            raise ConfigValidationError(
                "Invalid or placeholder API key. Please enter a valid key in config.json.\n"
                "尚未填写有效的 API 密钥，请编辑 config.json 填入正确的密钥。\n"
                "       Example/示例: \"api_key\": \"sk-xxxxxxxxxxxxxxxxxxxxxxxx\""
            )

        try:
            max_history = int(data.get("max_history", 10))
            timeout = int(data.get("timeout", 90))
            max_retries = int(data.get("max_retries", 3))
            retry_delay = float(data.get("retry_delay", 1.0))
        except (ValueError, TypeError) as e:
            raise ConfigValidationError(f"Invalid numeric config value: {e} / 数值配置项格式错误: {e}")

        default_size = str(data.get("default_size", self._TEMPLATE["default_size"])).strip()
        if default_size not in self.ALLOWED_SIZES:
            raise ConfigValidationError(
                f"Invalid default_size '{default_size}'. Allowed values: {', '.join(sorted(self.ALLOWED_SIZES))}\n"
                f"default_size 配置无效，可选值为: {', '.join(sorted(self.ALLOWED_SIZES))}"
            )

        return ConfigSchema(
            api_key=api_key,
            api_base=self._derive_api_base(data),
            base_url=str(data.get("base_url", self._TEMPLATE["base_url"])),
            model=model,
            image_dir=data.get("image_dir", self._TEMPLATE["image_dir"]),
            history_file=data.get("history_file", self._TEMPLATE["history_file"]),
            max_history=max_history,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            default_size=default_size
        )

    def load(self) -> ConfigSchema:
        """
        Load configuration from file. Creates template if missing.
        Caches result for subsequent calls.
        从文件加载配置。如果不存在则创建模板。
        缓存结果供后续调用使用。
        """
        if self._config is not None:
            return self._config

        if not self._config_path.exists():
            self._create_template()

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"config.json is corrupted: {e} / config.json 格式损坏: {e}")
        except OSError as e:
            raise ConfigValidationError(f"Cannot read config file: {e} / 无法读取配置文件: {e}")

        self._config = self._validate(raw)
        return self._config

    @property
    def config(self) -> ConfigSchema:
        """Access loaded configuration; loads if not already cached.
        访问已加载的配置；如果尚未缓存则加载。"""
        if self._config is None:
            return self.load()
        return self._config

    def reload(self) -> ConfigSchema:
        """Force reload configuration from disk.
        强制从磁盘重新加载配置。"""
        self._config = None
        return self.load()
