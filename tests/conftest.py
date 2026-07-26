"""Shared fixtures.

A QApplication must exist before any QWidget or QColor is constructed, and Qt
allows only one per process — so it is created once per session here rather
than per test.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Qt needs a platform plugin even when nothing is displayed. Set before the
# first Qt import or widget construction fails on headless machines.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session", autouse=True)
def qt_app() -> object:
    """Create the single QApplication the whole test session shares."""
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def square_svg(tmp_path: Path) -> str:
    """A 100x100 SVG whose content fills the entire viewport.

    Filling the viewport is what makes padding and zoom observable: any inset
    or scale applied by the renderer shows up as transparent border pixels.
    """
    path = tmp_path / "square.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<rect x="0" y="0" width="100" height="100" fill="#ff0000"/>'
        "</svg>",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def square_png(tmp_path: Path) -> str:
    """A 100x100 fully opaque red PNG, matching square_svg.

    Used to prove the PNG input path behaves the same as the SVG path.
    """
    from PIL import Image

    path = tmp_path / "square.png"
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(path)
    return str(path)
