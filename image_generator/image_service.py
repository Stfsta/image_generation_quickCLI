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
                    f"[Warning/警告] Unsupported size '{candidate_size}' / 不支持的尺寸 '{candidate_size}'. "
                    f"Supported sizes / 支持的尺寸: {', '.join(sorted(self.ALLOWED_SIZES))}"
                )
            prompt = re.sub(size_pattern, '', prompt).strip()
        
        return prompt, reference_image, parsed_size

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
                retry_delay=self.config.retry_delay
            )
        return self._client

    def _should_use_edits(self, reference_image: str) -> bool:
        """Decide whether local reference image can use edits endpoint.
        判断本地参考图是否可使用 edits 端点。"""
        if reference_image.startswith(("http://", "https://")):
            return False
        ref_path = Path(reference_image)
        if not ref_path.exists() or not ref_path.is_file():
            return False
        if ref_path.suffix.lower() != ".png":
            return False
        try:
            return ref_path.stat().st_size <= self.client.MAX_EDIT_IMAGE_BYTES
        except OSError:
            return False

    def generate(
        self,
        user_prompt: str,
        session_id: str = "default",
        size: str | None = None,
        n: int = 1,
        reference_image: str | None = None,
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
        ref_image = reference_image or parsed_image
        final_size = size or parsed_size or self.config.default_size

        full_prompt = self.history.build_context_prompt(parsed_prompt, session_id)
        truncated = full_prompt[:120] + "..." if len(full_prompt) > 120 else full_prompt
        
        if ref_image:
            print(f"[Prompt/提示词] {truncated}")
            print(f"[Reference/参考图] {ref_image}")
        else:
            print(f"[Prompt/提示词] {truncated}")

        if ref_image and self._should_use_edits(ref_image):
            gen_result: GenerationResult = self.client.edit(
                prompt=full_prompt,
                image_path=ref_image,
                size=final_size,
                n=n,
                **extra_params,
            )
        else:
            if ref_image and not ref_image.startswith(("http://", "https://")):
                print("[Info/信息] Local reference is not PNG<=4MB, fallback to generations private image_url path.")
                print("[Info/信息] 本地参考图不满足 PNG 且小于等于 4MB，已回退到 generations 私有 image_url 路径。")
            gen_result = self.client.generate(
                prompt=full_prompt,
                size=final_size,
                n=n,
                reference_image=ref_image,
                **extra_params,
            )

        if not gen_result.success:
            print(f"[Error/错误] {gen_result.error_message}")
            self.history.append(session_id, "system", "图像生成失败 / Image generation failed")
            return None

        if gen_result.usage:
            total_tokens = gen_result.usage.get("total_tokens")
            if total_tokens is not None:
                print(f"[Usage/用量] total_tokens={total_tokens}")

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
            print(f"[Saved/已保存] {dl_result.filepath}")
            self.history.append(session_id, "assistant", "图像已生成 / Image generated")
            return dl_result.filepath
        else:
            print(f"[Error/错误] {dl_result.error_message}")
            self.history.append(session_id, "system", "图像下载失败 / Image download failed")
            return None

    def clear_history(self, session_id: str = "default") -> None:
        """Clear conversation history for a session.
        清空会话的对话历史。"""
        self.history.clear(session_id)
        print(f"[Info/信息] Session '{session_id}' history cleared. / 会话 '{session_id}' 的历史记录已清空。")

    def close(self) -> None:
        """Release all resources.
        释放所有资源。"""
        if self._client is not None:
            self._client.close()

    def __enter__(self) -> "ImageGenerationService":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
