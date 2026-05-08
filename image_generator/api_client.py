"""
HTTP API client with connection pooling, retries, and structured error handling.
HTTP API 客户端，支持连接池、自动重试和结构化错误处理。
"""

from __future__ import annotations

import base64
import binascii
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class GenerationResult:
    """Result of an image generation/edit request.
    图像生成/编辑请求的结果。"""

    success: bool
    image_url: str | None = None
    image_b64: str | None = None
    usage: dict[str, Any] | None = None
    error_message: str | None = None
    status_code: int | None = None


@dataclass
class DownloadResult:
    """Result of local image persistence.
    图片本地保存结果。"""

    success: bool
    filepath: str | None = None
    error_message: str | None = None


class ImageAPIError(Exception):
    """Base exception for API client errors.
    API 客户端错误的基础异常类。"""


class ImageAPIClient:
    """
    High-performance API client with connection pooling, configurable retries,
    and comprehensive error handling.
    高性能 API 客户端，支持连接池、可配置重试和全面的错误处理。
    """

    GENERATIONS_PATH = "/v1/images/generations"
    EDITS_PATH = "/v1/images/edits"
    MAX_EDIT_IMAGE_BYTES = 4 * 1024 * 1024

    def __init__(
        self,
        api_key: str,
        api_base: str | None = None,
        model: str = "gpt-image-2",
        timeout: int = 90,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_base = self._normalize_api_base(api_base or base_url or "https://api.suchuang.vip")
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {api_key}"})

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _normalize_api_base(self, raw: str) -> str:
        """
        Normalize host/base URL and strip old hardcoded image endpoints.
        规范化 host/base URL，并剥离旧版完整端点路径。
        """
        api_base = raw.strip().rstrip("/")
        for suffix in (self.GENERATIONS_PATH, f"{self.GENERATIONS_PATH}/", self.EDITS_PATH, f"{self.EDITS_PATH}/"):
            if api_base.endswith(suffix.rstrip("/")):
                api_base = api_base[: -len(suffix.rstrip("/"))]
                break
        return api_base.rstrip("/")

    def _endpoint(self, path: str) -> str:
        return f"{self._api_base}{path}"

    def _encode_image(self, image_path: str) -> str:
        """
        Encode an image file to base64 data URI for generations private extension.
        将图片文件编码为 base64 data URI（用于 generations 私有扩展）。
        """
        file_path = Path(image_path)
        if not file_path.is_file():
            raise ImageAPIError(f"Reference image file does not exist: {file_path}")

        try:
            image_data = file_path.read_bytes()
        except OSError as e:
            raise ImageAPIError(f"Failed to read reference image file: {e}") from e

        ext = file_path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            mime_type = "image/jpeg"
        elif ext == ".png":
            mime_type = "image/png"
        elif ext == ".webp":
            mime_type = "image/webp"
        else:
            raise ImageAPIError(
                f"Unsupported image format '{ext}'. Supported formats: .jpg, .jpeg, .png, .webp"
            )

        encoded = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _parse_generation_response(self, resp: requests.Response) -> GenerationResult:
        try:
            data = resp.json()
        except ValueError:
            return GenerationResult(
                success=False,
                error_message=f"API returned non-JSON response / API 返回非 JSON 响应: HTTP {resp.status_code} - {resp.text}",
                status_code=resp.status_code,
            )

        images = data.get("data", [])
        if not images:
            return GenerationResult(
                success=False,
                error_message="API returned no image data / API 未返回任何图片数据。",
                status_code=resp.status_code,
            )

        first = images[0] if isinstance(images[0], dict) else {}
        image_url = first.get("url")
        image_b64 = first.get("b64_json")
        if image_url or image_b64:
            return GenerationResult(
                success=True,
                image_url=image_url,
                image_b64=image_b64,
                usage=data.get("usage"),
                status_code=resp.status_code,
            )

        return GenerationResult(
            success=False,
            error_message="API image payload missing url and b64_json / API 返回的图片数据中未包含 url 或 b64_json。",
            status_code=resp.status_code,
        )

    def _post_with_retry(
        self,
        url: str,
        *,
        json_payload: dict[str, Any] | None = None,
        data_payload: dict[str, Any] | None = None,
        files_payload: dict[str, tuple[str, BinaryIO, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response | None:
        last_exception: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.post(
                    url,
                    json=json_payload,
                    data=data_payload,
                    files=files_payload,
                    headers=headers,
                    timeout=self._timeout,
                )
                if resp.status_code == 429 and attempt < self._max_retries:
                    wait = self._retry_delay * (2 ** (attempt - 1))
                    time.sleep(wait)
                    continue
                return resp
            except requests.Timeout as e:
                last_exception = e
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)
                    continue
                raise
            except requests.RequestException as e:
                last_exception = e
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)
                    continue
                raise

        if last_exception:
            raise last_exception
        return None

    def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        reference_image: str | None = None,
        **extra_params: Any,
    ) -> GenerationResult:
        """
        Generate an image via `/v1/images/generations`.
        Supports url/b64_json response and private `image_url` extension fallback.
        通过 `/v1/images/generations` 生成图像。
        兼容 url/b64_json 响应，并支持私有 image_url 扩展。
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "n": n,
            "size": size,
            **extra_params,
        }

        if reference_image:
            if reference_image.startswith(("http://", "https://")):
                payload["image_url"] = reference_image
            else:
                try:
                    payload["image_url"] = self._encode_image(reference_image)
                except ImageAPIError as e:
                    return GenerationResult(success=False, error_message=f"Failed to process reference image / 处理参考图片失败: {e}")

        try:
            resp = self._post_with_retry(
                self._endpoint(self.GENERATIONS_PATH),
                json_payload=payload,
                headers={"Content-Type": "application/json"},
            )
        except requests.Timeout as e:
            return GenerationResult(success=False, error_message=f"Request timeout / 请求超时 (已重试 {self._max_retries} 次): {e}")
        except requests.RequestException as e:
            return GenerationResult(success=False, error_message=f"Network request error / 网络请求异常 (已重试 {self._max_retries} 次): {e}")

        if resp is None:
            return GenerationResult(success=False, error_message="Unknown error: no response / 未知错误：未收到响应")

        if resp.status_code != 200:
            return GenerationResult(
                success=False,
                error_message=f"API request failed / API 请求失败: HTTP {resp.status_code} - {resp.text}",
                status_code=resp.status_code,
            )

        return self._parse_generation_response(resp)

    def _validate_png_for_edit(self, image_path: str, field_name: str) -> Path:
        file_path = Path(image_path)
        if not file_path.is_file():
            raise ImageAPIError(f"{field_name} file does not exist: {file_path}")
        if file_path.suffix.lower() != ".png":
            raise ImageAPIError(f"{field_name} must be PNG: {file_path}")
        try:
            file_size = file_path.stat().st_size
        except OSError as e:
            raise ImageAPIError(f"Cannot stat {field_name} file: {e}") from e
        if file_size > self.MAX_EDIT_IMAGE_BYTES:
            raise ImageAPIError(
                f"{field_name} file is too large ({file_size} bytes). Must be <= {self.MAX_EDIT_IMAGE_BYTES} bytes."
            )
        return file_path

    def edit(
        self,
        prompt: str,
        image_path: str,
        size: str = "1024x1024",
        n: int = 1,
        mask_path: str | None = None,
        response_format: str = "b64_json",
        user: str | None = None,
        **extra_params: Any,
    ) -> GenerationResult:
        """
        Edit an image via `/v1/images/edits` using multipart/form-data.
        通过 `/v1/images/edits` 以 multipart/form-data 编辑图像。
        """
        try:
            image_file = self._validate_png_for_edit(image_path, "image")
            mask_file = self._validate_png_for_edit(mask_path, "mask") if mask_path else None
        except ImageAPIError as e:
            return GenerationResult(success=False, error_message=str(e))

        data_payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "n": str(n),
            "size": size,
            "response_format": response_format,
        }
        if user:
            data_payload["user"] = user
        for key, value in extra_params.items():
            if value is not None:
                data_payload[key] = value

        image_handle: BinaryIO | None = None
        mask_handle: BinaryIO | None = None
        try:
            image_handle = image_file.open("rb")
            files_payload: dict[str, tuple[str, BinaryIO, str]] = {
                "image": (image_file.name, image_handle, "image/png")
            }
            if mask_file is not None:
                mask_handle = mask_file.open("rb")
                files_payload["mask"] = (mask_file.name, mask_handle, "image/png")

            try:
                resp = self._post_with_retry(
                    self._endpoint(self.EDITS_PATH),
                    data_payload=data_payload,
                    files_payload=files_payload,
                )
            except requests.Timeout as e:
                return GenerationResult(success=False, error_message=f"Request timeout / 请求超时 (已重试 {self._max_retries} 次): {e}")
            except requests.RequestException as e:
                return GenerationResult(success=False, error_message=f"Network request error / 网络请求异常 (已重试 {self._max_retries} 次): {e}")
        finally:
            if image_handle:
                image_handle.close()
            if mask_handle:
                mask_handle.close()

        if resp is None:
            return GenerationResult(success=False, error_message="Unknown error: no response / 未知错误：未收到响应")

        if resp.status_code != 200:
            return GenerationResult(
                success=False,
                error_message=f"API request failed / API 请求失败: HTTP {resp.status_code} - {resp.text}",
                status_code=resp.status_code,
            )

        return self._parse_generation_response(resp)

    def download(self, url: str, image_dir: Path, filename: str | None = None) -> DownloadResult:
        """
        Download an image from URL.
        从 URL 下载图片。
        """
        if not url:
            return DownloadResult(success=False, error_message="Download URL is empty / 下载 URL 为空")

        try:
            if not filename:
                filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = image_dir / filename
            image_dir.mkdir(parents=True, exist_ok=True)
            with self._session.get(url, timeout=60, stream=True) as resp:
                resp.raise_for_status()
                filepath.write_bytes(resp.content)
            return DownloadResult(success=True, filepath=str(filepath))
        except requests.RequestException as e:
            return DownloadResult(success=False, error_message=f"Image download failed / 图片下载失败: {e}")
        except OSError as e:
            return DownloadResult(success=False, error_message=f"File save failed / 文件保存失败: {e}")

    def save_b64(self, image_b64: str, image_dir: Path, filename: str | None = None) -> DownloadResult:
        """
        Save image bytes from base64 payload to local file.
        将 base64 图片数据保存到本地文件。
        """
        if not image_b64:
            return DownloadResult(success=False, error_message="b64_json is empty / b64_json 内容为空")

        try:
            if not filename:
                filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = image_dir / filename
            image_dir.mkdir(parents=True, exist_ok=True)

            b64_payload = image_b64.split(",", 1)[1] if image_b64.startswith("data:") and "," in image_b64 else image_b64
            decoded = base64.b64decode(b64_payload, validate=True)
            filepath.write_bytes(decoded)
            return DownloadResult(success=True, filepath=str(filepath))
        except (binascii.Error, ValueError) as e:
            return DownloadResult(success=False, error_message=f"b64_json decode failed / b64_json 解码失败: {e}")
        except OSError as e:
            return DownloadResult(success=False, error_message=f"File save failed / 文件保存失败: {e}")

    def close(self) -> None:
        """Clean up session resources.
        清理会话资源。"""
        self._session.close()

    def __enter__(self) -> "ImageAPIClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
