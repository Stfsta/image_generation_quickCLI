"""
Portable Image Generation Tool - Modular Package

基于速创API中转站的便捷图像生成工具，支持对话上下文记忆。
"""

from .version import __version__
__all__ = ["ConfigManager", "HistoryManager", "ImageAPIClient", "ImageGenerationService"]

from .config import ConfigManager
from .history import HistoryManager
from .api_client import ImageAPIClient
from .image_service import ImageGenerationService
