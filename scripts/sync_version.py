"""
Sync displayed version strings from image_generator.version.__version__.
从 image_generator.version.__version__ 同步文档中的版本显示文本。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from image_generator.version import __version__


def _replace_or_raise(path: Path, pattern: str, replacement: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
    if count == 0:
        raise RuntimeError(f"Pattern not found in {path}: {pattern}")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    targets: list[tuple[Path, str, str]] = [
        (
            ROOT / "README.md",
            r"^# Suchuang API Image Generator \(e\.g\. GPT-image-2\) v[0-9]+\.[0-9]+\.[0-9]+$",
            f"# Suchuang API Image Generator (e.g. GPT-image-2) v{__version__}",
        ),
        (
            ROOT / "docs" / "README.zh-CN.md",
            r"^# 速创API 图像生成工具（e\.g\. GPT-image-2）v[0-9]+\.[0-9]+\.[0-9]+$",
            f"# 速创API 图像生成工具（e.g. GPT-image-2）v{__version__}",
        ),
        (
            ROOT / "docs" / "REPOSITORY_SNAPSHOT.md",
            r"(- \*\*名称\*\*：`image-generator`（仓库目录 `image_generation_quickCLI`），版本 `)[0-9]+\.[0-9]+\.[0-9]+(`。)",
            rf"\g<1>{__version__}\2",
        ),
        (
            ROOT / "docs" / "REPOSITORY_SNAPSHOT.md",
            r"(`__version__=\")[0-9]+\.[0-9]+\.[0-9]+(\")",
            rf"\g<1>{__version__}\2",
        ),
    ]

    for path, pattern, replacement in targets:
        _replace_or_raise(path, pattern, replacement)

    print(f"Synced visible version strings to {__version__}")


if __name__ == "__main__":
    main()

