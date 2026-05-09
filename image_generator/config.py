"""
Configuration management with validation and schema enforcement.
配置管理模块，支持验证和模式强制。
"""

import json
import sys
from pathlib import Path
from typing import Any
from dataclasses import dataclass, asdict

from .i18n import normalize_language, text


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
    language: str = "en"
    reference_dir: str = "./reference_images"
    multi_ref_mode: str = "direct"
    collage_max_refs: int = 4
    collage_layout: str = "auto"
    collage_canvas: int = 1024
    collage_annotate: bool = True
    collage_keep_temp: bool = False
    collage_prompt_hint: bool = True

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
    ALLOWED_MULTI_REF_MODES = {"off", "direct", "collage"}
    ALLOWED_COLLAGE_LAYOUTS = {"auto", "horizontal", "grid"}
    _TEMPLATE = {
        "api_key": "sk-your-api-key",
        "api_base": "https://api.suchuang.vip",
        "base_url": "https://api.suchuang.vip/v1/images/generations",
        "model": "gpt-image-2",
        "image_dir": "./generated_images",
        "reference_dir": "./reference_images",
        "history_file": "chat_memory.json",
        "max_history": 10,
        "timeout": 90,
        "max_retries": 3,
        "retry_delay": 1.0,
        "default_size": "1024x1024",
        "language": "en",
        "multi_ref_mode": "direct",
        "collage_max_refs": 4,
        "collage_layout": "auto",
        "collage_canvas": 1024,
        "collage_annotate": True,
        "collage_keep_temp": False,
        "collage_prompt_hint": True,
    }

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._config_path = Path(config_path) if config_path else self.CONFIG_FILE
        self._config: ConfigSchema | None = None

    def _create_template(self) -> None:
        """Generate a template configuration file and exit gracefully.
        生成模板配置文件并优雅退出。"""
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._TEMPLATE, f, ensure_ascii=False, indent=2)
        language = self._TEMPLATE["language"]
        print(text(language, "config_template_created", path=self._config_path))
        print(text(language, "config_template_edit"))
        print(text(language, "config_template_get_key"))
        sys.exit(0)

    def _derive_api_base(self, data: dict[str, Any], language: str) -> str:
        """Derive API host from api_base or legacy base_url.
        从 api_base 或旧 base_url 派生 API host。"""
        api_base = str(data.get("api_base", "")).strip()
        legacy_base_url = str(data.get("base_url", "")).strip()

        candidate = api_base or legacy_base_url or self._TEMPLATE["api_base"]
        candidate = candidate.rstrip("/")
        if "/v1/images/" in candidate:
            print(text(language, "config_legacy_base_url"))
            candidate = candidate.split("/v1/images/", 1)[0]
        return candidate.rstrip("/")

    def _validate(self, data: dict[str, Any]) -> ConfigSchema:
        """Validate raw configuration data against the schema.
        根据模式验证原始配置数据。"""
        language = normalize_language(str(data.get("language", self._TEMPLATE["language"])))
        required = ["api_key", "model"]
        missing = [key for key in required if key not in data or not data[key]]
        if missing:
            raise ConfigValidationError(text(language, "config_missing_fields", fields=", ".join(missing)))

        api_key = str(data.get("api_key", ""))
        model = str(data.get("model", "")).strip()
        if not model:
            raise ConfigValidationError(text(language, "config_missing_model"))

        if api_key.startswith("sk-your-") or api_key.startswith("sk-在此填写") or len(api_key) < 20:
            raise ConfigValidationError(text(language, "config_invalid_api_key"))

        try:
            max_history = int(data.get("max_history", 10))
            timeout = int(data.get("timeout", 90))
            max_retries = int(data.get("max_retries", 3))
            retry_delay = float(data.get("retry_delay", 1.0))
            collage_max_refs = int(data.get("collage_max_refs", self._TEMPLATE["collage_max_refs"]))
            collage_canvas = int(data.get("collage_canvas", self._TEMPLATE["collage_canvas"]))
        except (ValueError, TypeError) as e:
            raise ConfigValidationError(text(language, "config_invalid_numeric", error=e))

        default_size = str(data.get("default_size", self._TEMPLATE["default_size"])).strip()
        if default_size not in self.ALLOWED_SIZES:
            raise ConfigValidationError(
                text(
                    language,
                    "config_invalid_default_size",
                    value=default_size,
                    allowed=", ".join(sorted(self.ALLOWED_SIZES)),
                )
            )

        raw_language = str(data.get("language", self._TEMPLATE["language"])).strip().lower()
        if raw_language not in ("en", "zh"):
            raise ConfigValidationError(text(language, "config_invalid_language", value=raw_language))

        multi_ref_mode = str(data.get("multi_ref_mode", self._TEMPLATE["multi_ref_mode"])).strip().lower()
        if multi_ref_mode not in self.ALLOWED_MULTI_REF_MODES:
            raise ConfigValidationError(
                text(
                    language,
                    "config_invalid_multi_ref_mode",
                    value=multi_ref_mode,
                    allowed=", ".join(sorted(self.ALLOWED_MULTI_REF_MODES)),
                )
            )

        collage_layout = str(data.get("collage_layout", self._TEMPLATE["collage_layout"])).strip().lower()
        if collage_layout not in self.ALLOWED_COLLAGE_LAYOUTS:
            raise ConfigValidationError(
                text(
                    language,
                    "config_invalid_collage_layout",
                    value=collage_layout,
                    allowed=", ".join(sorted(self.ALLOWED_COLLAGE_LAYOUTS)),
                )
            )

        if collage_max_refs < 2 or collage_max_refs > 9:
            raise ConfigValidationError(
                text(language, "config_invalid_collage_max_refs", value=collage_max_refs)
            )

        if collage_canvas < 512 or collage_canvas > 2048:
            raise ConfigValidationError(
                text(language, "config_invalid_collage_canvas", value=collage_canvas)
            )

        raw_annotate = data.get("collage_annotate", self._TEMPLATE["collage_annotate"])
        raw_keep_temp = data.get("collage_keep_temp", self._TEMPLATE["collage_keep_temp"])
        raw_prompt_hint = data.get("collage_prompt_hint", self._TEMPLATE["collage_prompt_hint"])
        if not isinstance(raw_annotate, bool):
            raise ConfigValidationError(text(language, "config_invalid_boolean", field="collage_annotate"))
        if not isinstance(raw_keep_temp, bool):
            raise ConfigValidationError(text(language, "config_invalid_boolean", field="collage_keep_temp"))
        if not isinstance(raw_prompt_hint, bool):
            raise ConfigValidationError(text(language, "config_invalid_boolean", field="collage_prompt_hint"))

        return ConfigSchema(
            api_key=api_key,
            api_base=self._derive_api_base(data, language),
            base_url=str(data.get("base_url", self._TEMPLATE["base_url"])),
            model=model,
            image_dir=data.get("image_dir", self._TEMPLATE["image_dir"]),
            reference_dir=data.get("reference_dir", self._TEMPLATE["reference_dir"]),
            history_file=data.get("history_file", self._TEMPLATE["history_file"]),
            max_history=max_history,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            default_size=default_size,
            language=raw_language,
            multi_ref_mode=multi_ref_mode,
            collage_max_refs=collage_max_refs,
            collage_layout=collage_layout,
            collage_canvas=collage_canvas,
            collage_annotate=raw_annotate,
            collage_keep_temp=raw_keep_temp,
            collage_prompt_hint=raw_prompt_hint,
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
            raise ConfigValidationError(text("en", "config_corrupted_json", error=e))
        except OSError as e:
            raise ConfigValidationError(text("en", "config_read_error", error=e))

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

    def save_updates(self, **updates: Any) -> ConfigSchema:
        """
        Persist selected configuration fields to config.json and refresh cache.
        将指定配置字段写回 config.json 并刷新缓存。
        """
        if not self._config_path.exists():
            self._create_template()

        with open(self._config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        raw.update(updates)
        validated = self._validate(raw)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(validated.to_dict(), f, ensure_ascii=False, indent=2)
        self._config = validated
        return validated
