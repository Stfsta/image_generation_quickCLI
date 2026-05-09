from pathlib import Path

import pytest
from PIL import Image

from image_generator.reference_collage import CollageError, CollageOptions, compose_reference_collage


def _make_image(path: Path, color: tuple[int, int, int]) -> str:
    image = Image.new("RGB", (320, 240), color)
    image.save(path, format="PNG")
    return str(path)


def test_compose_reference_collage_generates_png(tmp_path):
    refs = [
        _make_image(tmp_path / "a.png", (255, 0, 0)),
        _make_image(tmp_path / "b.png", (0, 255, 0)),
        _make_image(tmp_path / "c.png", (0, 0, 255)),
    ]

    result = compose_reference_collage(refs, CollageOptions(max_refs=4, layout="auto", canvas=1024, annotate=True))
    output_path = Path(result.path)
    assert output_path.exists()
    assert output_path.suffix.lower() == ".png"
    assert result.used_count == 3
    assert result.omitted_count == 0
    assert len(result.label_mapping) == 3
    assert result.file_size <= 4 * 1024 * 1024
    output_path.unlink(missing_ok=True)


def test_compose_reference_collage_truncates_by_max_refs(tmp_path):
    refs = [
        _make_image(tmp_path / "a.png", (255, 0, 0)),
        _make_image(tmp_path / "b.png", (0, 255, 0)),
        _make_image(tmp_path / "c.png", (0, 0, 255)),
    ]

    result = compose_reference_collage(refs, CollageOptions(max_refs=2, layout="horizontal", canvas=1024))
    assert result.used_count == 2
    assert result.omitted_count == 1
    Path(result.path).unlink(missing_ok=True)


def test_compose_reference_collage_raises_for_missing_file(tmp_path):
    with pytest.raises(CollageError):
        compose_reference_collage([str(tmp_path / "missing.png")], CollageOptions())
