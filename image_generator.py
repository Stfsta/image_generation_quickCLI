"""
速创API 图像生成工具（gpt-image-2）- 兼容入口

此文件保留向后兼容性，内部实现已迁移至 image_generator 包。

Suchuang API image generation tool (gpt-image-2) - compatibility entry

This file is kept for backward compatibility. Internal implementation has been migrated to the image_generator package.
"""

from image_generator.cli import main

if __name__ == "__main__":
    main()
