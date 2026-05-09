"""
High-level image generation service orchestrating config, history, and API client.
高级图像生成服务，协调配置、历史和 API 客户端。
"""

import re
from pathlib import Path
from typing import Any

from .config import ConfigManager, ConfigSchema
from .history import HistoryManager
from .api_client import ImageAPIClient, GenerationResult, DownloadResult
from .reference_collage import CollageError, CollageOptions, compose_reference_collage
from .i18n import text


class ImageGenerationService:
    ALLOWED_SIZES = ConfigManager.ALLOWED_SIZES

    """
    Orchestration layer that combines configuration, conversation history,
    and API communication into a cohesive image generation workflow.
    编排层，将配置、对话历史和 API 通信组合成一个连贯的图像生成工作流。
    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        history_manager: HistoryManager | None = None,
        api_client: ImageAPIClient | None = None
    ) -> None:
        self._config_manager = config_manager or ConfigManager()
        self._cfg: ConfigSchema | None = None
        self._history: HistoryManager | None = history_manager
        self._client: ImageAPIClient | None = api_client

    @property
    def language(self) -> str:
        return self.config.language

    def set_language(self, language: str) -> None:
        self._cfg = self._config_manager.save_updates(language=language)
        if self._client is not None:
            self._client.set_language(self._cfg.language)

    def _parse_prompt(self, prompt: str) -> tuple[str, str | None, str | None]:
        """
        Parse the prompt to extract image references and size tags.
        Supports [image:path] and [size:WxH] syntax in the prompt.
        Returns (clean_prompt, reference_image_path_or_url, size_or_none).
        解析提示词以提取图像引用和尺寸标签。
        支持提示词中的 [image:path] 和 [size:宽x高] 语法。
        返回 (清理后的提示词, 参考图片路径或URL, 尺寸或None)。
        """
        image_pattern = r'\[image:([^\]]+)\]'
        size_pattern = r'\[size:([^\]]+)\]'
        matches = re.findall(image_pattern, prompt)
        size_matches = re.findall(size_pattern, prompt)
        
        reference_image = None
        if matches:
            reference_image = matches[0].strip()
            prompt = re.sub(image_pattern, '', prompt).strip()

        parsed_size = None
        if size_matches:
            candidate_size = size_matches[0].strip().lower()
            if candidate_size in self.ALLOWED_SIZES:
                parsed_size = candidate_size
            else:
                print(
                    text(
                        self.language,
                        "service_warn_invalid_size",
                        size=candidate_size,
                        allowed=", ".join(sorted(self.ALLOWED_SIZES)),
                    )
                )
            prompt = re.sub(size_pattern, '', prompt).strip()
        
        return prompt, reference_image, parsed_size

    def _is_url_reference(self, value: str) -> bool:
        return value.startswith(("http://", "https://"))

    def _build_collage_hint(self, mapping: list[tuple[str, str]]) -> str:
        if not mapping:
            return ""
        pairs = ", ".join([f"{label}={Path(path).name}" for label, path in mapping])
        if self.language == "zh":
            return f"参考拼贴图标注映射：{pairs}。请按这些标注理解多图关系并进行编辑。"
        return f"Reference collage label mapping: {pairs}. Use these labels when applying cross-image edits."

    @property
    def config(self) -> ConfigSchema:
        """Lazy-load and cache configuration.
        延迟加载并缓存配置。"""
        if self._cfg is None:
            self._cfg = self._config_manager.load()
        return self._cfg

    @property
    def history(self) -> HistoryManager:
        """Lazy-initialize history manager.
        延迟初始化历史管理器。"""
        if self._history is None:
            self._history = HistoryManager(
                history_file=self.config.history_file,
                max_history=self.config.max_history
            )
        return self._history

    @property
    def client(self) -> ImageAPIClient:
        """Lazy-initialize API client.
        延迟初始化 API 客户端。"""
        if self._client is None:
            self._client = ImageAPIClient(
                api_key=self.config.api_key,
                api_base=self.config.api_base,
                base_url=self.config.base_url,
                model=self.config.model,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
                retry_delay=self.config.retry_delay,
                language=self.language,
            )
        return self._client

    def _resolve_auto_reference_images(self) -> list[str]:
        ref_dir = Path(self.config.reference_dir)
        if not ref_dir.exists() or not ref_dir.is_dir():
            return []
        candidates = [
            path for path in ref_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]
        if not candidates:
            return []
        sorted_candidates = sorted(candidates, key=lambda p: (p.stat().st_mtime, p.name))
        resolved = [str(path) for path in sorted_candidates]
        print(
            text(
                self.language,
                "service_auto_ref_detected",
                count=len(resolved),
                directory=ref_dir.resolve(),
            )
        )
        return resolved

    def _should_use_edits(self, reference_images: list[str]) -> bool:
        """Decide whether local reference image can use edits endpoint.
        判断本地参考图是否可使用 edits 端点。"""
        if not reference_images:
            return False
        for reference_image in reference_images:
            if reference_image.startswith(("http://", "https://")):
                return False
            ref_path = Path(reference_image)
            if not ref_path.exists() or not ref_path.is_file():
                return False
            if ref_path.suffix.lower() != ".png":
                return False
            try:
                if ref_path.stat().st_size > self.client.MAX_EDIT_IMAGE_BYTES:
                    return False
            except OSError:
                return False
        return True

    def generate(
        self,
        user_prompt: str,
        session_id: str = "default",
        size: str | None = None,
        n: int = 1,
        reference_image: str | list[str] | None = None,
        **extra_params: Any
    ) -> str | None:
        """
        End-to-end image generation with context awareness.
        Supports image-to-image generation via reference_image parameter or [image:path] syntax.
        Returns the saved file path on success, None on failure.
        端到端的图像生成，支持上下文感知。
        通过 reference_image 参数或 [image:path] 语法支持图生图功能。
        成功时返回保存的文件路径，失败时返回 None。
        """
        self.history.append(session_id, "user", user_prompt)

        parsed_prompt, parsed_image, parsed_size = self._parse_prompt(user_prompt)
        resolved_ref: str | list[str] | None = reference_image or parsed_image
        if not resolved_ref:
            auto_refs = self._resolve_auto_reference_images()
            if auto_refs:
                resolved_ref = auto_refs

        if isinstance(resolved_ref, str):
            references = [resolved_ref]
        elif isinstance(resolved_ref, list):
            references = [ref for ref in resolved_ref if ref]
        else:
            references = []

        temp_collage_path: Path | None = None
        if len(references) > 1:
            mode = self.config.multi_ref_mode
            if mode == "off":
                print(text(self.language, "service_multi_ref_off", count=len(references)))
                references = [references[0]]
            elif mode == "collage":
                if any(self._is_url_reference(ref) for ref in references):
                    print(text(self.language, "service_collage_skip_url_ref"))
                else:
                    try:
                        collage_result = compose_reference_collage(
                            references,
                            CollageOptions(
                                max_refs=self.config.collage_max_refs,
                                layout=self.config.collage_layout,
                                canvas=self.config.collage_canvas,
                                annotate=self.config.collage_annotate,
                                max_bytes=self.client.MAX_EDIT_IMAGE_BYTES,
                            ),
                        )
                        temp_collage_path = Path(collage_result.path)
                        references = [str(temp_collage_path)]
                        if self.config.collage_prompt_hint and collage_result.label_mapping:
                            parsed_prompt = f"{self._build_collage_hint(collage_result.label_mapping)}\n{parsed_prompt}"
                        print(
                            text(
                                self.language,
                                "service_collage_composed",
                                used=collage_result.used_count,
                                omitted=collage_result.omitted_count,
                                path=collage_result.path,
                                bytes=collage_result.file_size,
                            )
                        )
                    except CollageError as e:
                        print(text(self.language, "service_collage_failed_fallback", error=e))

        final_size = size or parsed_size or self.config.default_size

        full_prompt = self.history.build_context_prompt(parsed_prompt, session_id, self.language)
        truncated = full_prompt[:120] + "..." if len(full_prompt) > 120 else full_prompt

        if references:
            print(text(self.language, "service_prompt", prompt=truncated))
            if len(references) == 1:
                print(text(self.language, "service_reference_single", reference=references[0]))
            else:
                print(text(self.language, "service_reference_multi", count=len(references)))
        else:
            print(text(self.language, "service_prompt", prompt=truncated))

        try:
            if references and self._should_use_edits(references):
                gen_result: GenerationResult = self.client.edit(
                    prompt=full_prompt,
                    image_path=references if len(references) > 1 else references[0],
                    size=final_size,
                    n=n,
                    **extra_params,
                )
            else:
                if references and any(not ref.startswith(("http://", "https://")) for ref in references):
                    print(text(self.language, "service_info_fallback_to_generations"))
                gen_result = self.client.generate(
                    prompt=full_prompt,
                    size=final_size,
                    n=n,
                    reference_image=references if len(references) > 1 else (references[0] if references else None),
                    **extra_params,
                )
        finally:
            if temp_collage_path and temp_collage_path.exists() and not self.config.collage_keep_temp:
                try:
                    temp_collage_path.unlink()
                except OSError:
                    pass

        if not gen_result.success:
            print(text(self.language, "service_error", error=gen_result.error_message))
            self.history.append(session_id, "system", text(self.language, "service_history_generation_failed"))
            return None

        if gen_result.usage:
            total_tokens = gen_result.usage.get("total_tokens")
            if total_tokens is not None:
                print(text(self.language, "service_usage", tokens=total_tokens))

        image_dir = Path(self.config.image_dir)
        if gen_result.image_b64:
            dl_result: DownloadResult = self.client.save_b64(
                image_b64=gen_result.image_b64,
                image_dir=image_dir,
            )
        else:
            dl_result = self.client.download(
                url=gen_result.image_url or "",
                image_dir=image_dir,
            )

        if dl_result.success:
            print(text(self.language, "service_saved", path=dl_result.filepath))
            self.history.append(session_id, "assistant", text(self.language, "service_history_generated"))
            return dl_result.filepath
        else:
            print(text(self.language, "service_error", error=dl_result.error_message))
            self.history.append(session_id, "system", text(self.language, "service_history_download_failed"))
            return None

    def clear_history(self, session_id: str = "default") -> None:
        """Clear conversation history for a session.
        清空会话的对话历史。"""
        self.history.clear(session_id)
        print(text(self.language, "service_clear_history", session_id=session_id))

    def close(self) -> None:
        """Release all resources.
        释放所有资源。"""
        if self._client is not None:
            self._client.close()

    def __enter__(self) -> "ImageGenerationService":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
