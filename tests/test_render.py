"""Regression tests for the three defects found by independent review.

Each test names the bug it pins. They are written against the SVG path first,
which was always correct, so the assertion doubles as a statement of the
behaviour the PNG path is supposed to match.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor

import svg_converter as sc

RED = (255, 0, 0)
BLUE = (0, 0, 255)
TARGET = 100


def _corner(img: object) -> tuple[int, ...]:
    """Top-left pixel — outside the content when padding or zoom applies."""
    return tuple(img.getpixel((0, 0)))  # type: ignore[attr-defined]


def _centre(img: object) -> tuple[int, ...]:
    return tuple(img.getpixel((TARGET // 2, TARGET // 2)))  # type: ignore[attr-defined]


# ── bug 1: PNG inputs ignored zoom and padding ──────────────────────────


def test_svg_padding_insets_content(square_svg: str) -> None:
    """Baseline: the SVG path has always honoured padding."""
    img = sc.render_svg_to_pillow(square_svg, TARGET, TARGET, padding=20, transparent=True)
    assert _corner(img)[3] == 0, "padding should leave the corner transparent"
    assert _centre(img)[:3] == RED


def test_png_padding_insets_content(square_png: str) -> None:
    """Bug 1: padding was dropped, so the image filled edge to edge."""
    img = sc.render_png_to_pillow(square_png, TARGET, TARGET, padding=20, transparent=True)
    assert _corner(img)[3] == 0, "padding must leave the corner transparent"
    assert _centre(img)[:3] == RED


def test_png_zoom_shrinks_content(square_png: str) -> None:
    """Bug 1: zoom was dropped, so the image always filled the canvas."""
    img = sc.render_png_to_pillow(square_png, TARGET, TARGET, zoom=0.5, transparent=True)
    assert _corner(img)[3] == 0, "zoom 0.5 must leave the corner transparent"
    assert _centre(img)[:3] == RED


def test_png_zoom_never_overscales(square_png: str) -> None:
    """Zoom above 1.0 is clamped, matching the SVG renderer."""
    at_one = sc.render_png_to_pillow(square_png, TARGET, TARGET, zoom=1.0)
    above = sc.render_png_to_pillow(square_png, TARGET, TARGET, zoom=5.0)
    assert at_one.size == above.size == (TARGET, TARGET)


# ── bug 2: opaque export ignored the chosen background colour ───────────


def test_png_opaque_uses_chosen_background(square_png: str) -> None:
    """Bug 2: convert("RGB") composited onto black, discarding bg_color."""
    img = sc.render_png_to_pillow(
        square_png,
        TARGET,
        TARGET,
        padding=20,
        transparent=False,
        bg_color=QColor("blue"),
    )
    assert img.mode == "RGB"
    assert _corner(img) == BLUE, "padding area must use the selected background"
    assert _centre(img) == RED


def test_svg_opaque_uses_chosen_background(square_svg: str) -> None:
    """Baseline: the SVG path already did this correctly."""
    img = sc.render_svg_to_pillow(
        square_svg,
        TARGET,
        TARGET,
        padding=20,
        transparent=False,
        bg_color=QColor("blue"),
    )
    assert _corner(img) == BLUE


# ── bug 3: .iconset filenames iconutil does not accept ──────────────────


def test_iconset_entries_are_valid_iconutil_names() -> None:
    """Bug 3: icon_64x64.png and icon_1024x1024.png are not valid members."""
    entries = sc.macos_iconset_entries(sc.MAC_ICON_SIZES)
    names = {name for name, _ in entries}

    valid = set()
    for pt in (16, 32, 128, 256, 512):
        valid.add(f"icon_{pt}x{pt}.png")
        valid.add(f"icon_{pt}x{pt}@2x.png")

    assert names == valid
    assert "icon_64x64.png" not in names
    assert "icon_1024x1024.png" not in names


def test_iconset_entries_pixel_sizes_match_names() -> None:
    """An @2x entry must be rendered at twice its point size."""
    for name, px in sc.macos_iconset_entries(sc.MAC_ICON_SIZES):
        point = int(name.split("_")[1].split("x")[0])
        expected = point * 2 if "@2x" in name else point
        assert px == expected, f"{name} should be {expected}px, got {px}"


# ── existing behaviour that must not regress ────────────────────────────


def test_unique_path_avoids_collision(tmp_path: Path) -> None:
    target = tmp_path / "icon.ico"
    target.write_bytes(b"x")
    assert sc.unique_path(target).name == "icon_1.ico"


def test_pillow_flatten_composites_onto_background() -> None:
    from PIL import Image

    transparent = Image.new("RGBA", (10, 10), (255, 0, 0, 0))
    flat = sc.pillow_flatten(transparent, (0, 0, 255, 255))
    assert flat.mode == "RGB"
    assert flat.getpixel((5, 5)) == BLUE


@pytest.mark.parametrize("fmt_sizes", [[16, 32], [64]])
def test_save_windows_ico_writes_file(
    square_svg: str, tmp_path: Path, fmt_sizes: list[int]
) -> None:
    sc.save_windows_ico(square_svg, tmp_path, fmt_sizes, True, 1.0, 0, QColor("white"))
    assert (tmp_path / "icon.ico").exists()
