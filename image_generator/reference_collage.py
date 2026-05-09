"""
Reference image collage utilities for pseudo multi-reference workflows.
多参考图拼接工具，用于伪多参考图工作流。
"""

from __future__ import annotations

import math
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


MAX_EDIT_IMAGE_BYTES = 4 * 1024 * 1024
_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class CollageError(Exception):
    """Raised when collage composition fails.
    当拼图合成失败时抛出。"""


@dataclass(frozen=True)
class CollageOptions:
    max_refs: int = 4
    layout: str = "auto"
    canvas: int = 1024
    annotate: bool = True
    max_bytes: int = MAX_EDIT_IMAGE_BYTES


@dataclass(frozen=True)
class CollageResult:
    path: str
    label_mapping: list[tuple[str, str]]
    used_count: int
    omitted_count: int
    final_canvas: int
    file_size: int


def _resolve_grid(count: int, layout: str) -> tuple[int, int]:
    if layout == "horizontal":
        return count, 1
    if layout == "grid":
        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)
        return cols, rows
    if count <= 2:
        return count, 1
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    return cols, rows


def _draw_label(draw: ImageDraw.ImageDraw, x: int, y: int, label: str) -> None:
    pad = 6
    text_bbox = draw.textbbox((0, 0), label)
    text_w = max(12, text_bbox[2] - text_bbox[0])
    text_h = max(12, text_bbox[3] - text_bbox[1])
    draw.rectangle(
        [x, y, x + text_w + pad * 2, y + text_h + pad * 2],
        fill=(0, 0, 0, 180),
    )
    draw.text((x + pad, y + pad), label, fill=(255, 255, 255, 255))


def compose_reference_collage(reference_paths: list[str], options: CollageOptions) -> CollageResult:
    if not reference_paths:
        raise CollageError("No reference images provided.")
    if options.max_refs < 2:
        raise CollageError("max_refs must be >= 2.")

    selected = reference_paths[: options.max_refs]
    omitted = max(0, len(reference_paths) - len(selected))
    resolved_paths = [Path(path) for path in selected]
    missing = [str(path) for path in resolved_paths if not path.is_file()]
    if missing:
        raise CollageError(f"Missing reference image(s): {', '.join(missing)}")

    cols, rows = _resolve_grid(len(resolved_paths), options.layout)
    gutter = 12
    canvas = options.canvas

    working_canvas = Image.new("RGBA", (canvas, canvas), (245, 245, 245, 255))
    tile_w = max(1, (canvas - gutter * (cols + 1)) // cols)
    tile_h = max(1, (canvas - gutter * (rows + 1)) // rows)

    label_mapping: list[tuple[str, str]] = []
    draw = ImageDraw.Draw(working_canvas, "RGBA")

    for index, path in enumerate(resolved_paths):
        try:
            with Image.open(path) as image:
                tile = ImageOps.contain(image.convert("RGB"), (tile_w, tile_h), Image.Resampling.LANCZOS)
        except OSError as e:
            raise CollageError(f"Cannot decode image '{path}': {e}") from e

        col = index % cols
        row = index // cols
        x = gutter + col * (tile_w + gutter)
        y = gutter + row * (tile_h + gutter)
        offset_x = x + (tile_w - tile.width) // 2
        offset_y = y + (tile_h - tile.height) // 2
        working_canvas.paste(tile, (offset_x, offset_y))

        if options.annotate:
            label = _LABELS[index] if index < len(_LABELS) else f"R{index + 1}"
            _draw_label(draw, x + 6, y + 6, label)
            label_mapping.append((label, str(path)))

    tmp = tempfile.NamedTemporaryFile(prefix="ref_collage_", suffix=".png", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    current = working_canvas
    current_canvas = canvas
    while True:
        current.save(tmp_path, format="PNG", optimize=True)
        file_size = tmp_path.stat().st_size
        if file_size <= options.max_bytes:
            return CollageResult(
                path=str(tmp_path),
                label_mapping=label_mapping,
                used_count=len(resolved_paths),
                omitted_count=omitted,
                final_canvas=current_canvas,
                file_size=file_size,
            )

        next_canvas = int(current_canvas * 0.88)
        if next_canvas < 512:
            raise CollageError(
                f"Collage is still larger than {options.max_bytes} bytes after compression attempts."
            )
        current_canvas = next_canvas
        current = current.resize((current_canvas, current_canvas), Image.Resampling.LANCZOS)
