import sys, os, io, platform, subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QColor, QPixmap, QImage
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QFileDialog, QVBoxLayout,
    QHBoxLayout, QComboBox, QSpinBox, QFormLayout, QLineEdit, QMessageBox,
    QCheckBox, QColorDialog, QSlider, QLabel
)

from PIL import Image
try:
    import cairosvg
except OSError as e:
    import platform
    sys_platform = platform.system()
    msg = [
        "\nERROR: The Cairo graphics library required by CairoSVG is not installed.",
        str(e),
        "\nTo fix this, follow the instructions for your platform:\n"
    ]
    if sys_platform == "Darwin":
        msg.append("macOS: Run 'brew install cairo' in Terminal. If you don't have Homebrew, install it from https://brew.sh first.")
    elif sys_platform == "Windows":
        msg.append("Windows: Install GTK3 and Cairo using MSYS2 or download prebuilt binaries. See https://pycairo.readthedocs.io/en/latest/getting_started.html#windows.")
    else:
        msg.append("Linux: Run 'sudo apt-get install libcairo2' or use your distro's package manager.")
    print("\n".join(msg), file=sys.stderr)
    sys.exit(1)


# ---------- Pillow LANCZOS compatibility ----------
try:
    LANCZOS_RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    LANCZOS_RESAMPLE = 1  # Pillow<10 fallback


# ---------- Presets (same as big GUI) ----------
WINDOWS_ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
MAC_ICON_SIZES     = [16, 32, 64, 128, 256, 512, 1024]
LINUX_ICON_SIZES   = [16, 22, 24, 32, 48, 64, 96, 128, 256, 512]
ANDROID_ICON_SIZES = [48, 72, 96, 144, 192, 512]
IOS_ICON_SIZES     = [60, 76, 120, 152, 167, 180, 1024]

DESKTOP_WALLPAPERS          = [QSize(1280, 720), QSize(1920, 1080), QSize(2560, 1440), QSize(3840, 2160)]
PHONE_WALLPAPERS            = [QSize(750, 1334), QSize(1080, 1920), QSize(1170, 2532), QSize(1440, 3040)]
TABLET_PORTRAIT_WALLPAPERS  = [QSize(1536, 2048), QSize(1668, 2388), QSize(1600, 2560)]
TABLET_LANDSCAPE_WALLPAPERS = [QSize(2048, 1536), QSize(2388, 1668), QSize(2560, 1600)]


# ---------- Utilities ----------
def unique_path(path: Path) -> Path:
    """Return a unique path if file exists."""
    counter = 1
    new_path = path
    while new_path.exists():
        new_path = path.with_stem(f"{path.stem}_{counter}")
        counter += 1
    return new_path

def qcolor_to_rgba_tuple(c: QColor) -> tuple[int, int, int, int]:
    return (c.red(), c.green(), c.blue(), c.alpha())

def pillow_flatten(img: Image.Image, bg_rgba: tuple[int,int,int,int]) -> Image.Image:
    """Flatten any image onto an opaque RGB background (needed for JPG/BMP/PDF)."""
    if img.mode != "RGBA":
        return img.convert("RGB")
    # Use only RGB for background, ignore alpha
    bg_rgb = bg_rgba[:3]
    bg = Image.new("RGB", img.size, bg_rgb)
    img_rgb = img.convert("RGB")
    bg.paste(img_rgb, mask=img.split()[3])  # Use alpha channel as mask
    return bg

def pillow_to_qpixmap(img: Image.Image) -> QPixmap:
    """Convert Pillow Image to QPixmap for preview."""
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qimg = QImage.fromData(buf.getvalue())  # Removed format string for Pylance type compatibility
    return QPixmap.fromImage(qimg)


# ---------- CairoSVG-based rendering (single source of truth) ----------
def render_svg_to_pillow(svg_path: str,
                         width: int, height: int,
                         zoom: float = 1.0,
                         padding: int = 0,
                         transparent: bool = True,
                         bg_color: Optional[QColor] = None) -> Image.Image:
    """
    Render SVG -> PNG bytes (CairoSVG), load into Pillow.

    Zoom semantics:
      - 1.0 = full fit inside (width,height) minus padding
      - 0.1..1.0 = shrink proportionally
      - never exceeds full fit (no overscale)
    """
    bg = bg_color if bg_color is not None else QColor("white")

    # Clamp zoom to [0.1, 1.0] so we only zoom OUT (never overscale)
    zoom = max(0.1, min(1.0, zoom))

    # Content area inside padding
    canvas_w = max(1, width)
    canvas_h = max(1, height)
    work_w = max(1, canvas_w - 2*padding)
    work_h = max(1, canvas_h - 2*padding)

    # Render size respects zoom relative to work area
    render_w = int(max(1, work_w * zoom))
    render_h = int(max(1, work_h * zoom))

    # CairoSVG render
    png_bytes = cairosvg.svg2png(
        url=svg_path,
        output_width=render_w,
        output_height=render_h,
        background_color=None if transparent else f"rgb({bg.red()},{bg.green()},{bg.blue()})"
    )
    content = Image.open(io.BytesIO(png_bytes if png_bytes is not None else b""))
    content.load()
    content = content.convert("RGBA" if transparent else "RGB")

    # Safety: if computed size slightly exceeds work area due to rounding
    cw, ch = content.size
    scale = min(work_w / cw, work_h / ch, 1.0)
    if scale < 1.0:
        new_size = (max(1, int(cw*scale)), max(1, int(ch*scale)))
        content = content.resize(new_size, LANCZOS_RESAMPLE)

    # Canvas
    if transparent:
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        # Center composite
        cx = (canvas_w - content.size[0]) // 2
        cy = (canvas_h - content.size[1]) // 2
        if canvas.mode == "RGBA" and content.mode == "RGBA":
            canvas.alpha_composite(content, (cx, cy))
        else:
            canvas.paste(content, (cx, cy))
        return canvas
    else:
        # Always flatten onto RGB background, using the background color
        canvas = Image.new("RGB", (canvas_w, canvas_h), (bg.red(), bg.green(), bg.blue()))
        cx = (canvas_w - content.size[0]) // 2
        cy = (canvas_h - content.size[1]) // 2
        # If content has alpha, use it as mask
        if content.mode == "RGBA":
            canvas.paste(content.convert("RGB"), (cx, cy), mask=content.split()[3])
        else:
            canvas.paste(content, (cx, cy))
        return canvas


# ---------- EXPORTS ----------
def save_windows_ico(svg_path: str, out_dir: Path, sizes: list[int], transparent: bool,
                     zoom: float, padding: int, bg: QColor):
    """
    Single Pillow image saved once with sizes=[...].
    Background is already applied by render step when transparent=False.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    base = max(sizes)
    src = render_svg_to_pillow(svg_path, base, base, zoom=zoom, padding=padding,
                               transparent=transparent, bg_color=bg)
    if not transparent:
        # Always convert to RGB, dropping any alpha channel
        if src.mode != "RGB":
            src = src.convert("RGB")
    ico_path = unique_path(out_dir / "icon.ico")
    src.save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])

def save_macos_icns(svg_path: str, out_dir: Path, sizes_for_check: list[int],
                    transparent: bool, zoom: float, padding: int, bg: QColor):
    """
    Save ICNS directly via Pillow from the same base image.
    Fallback to iconutil on macOS ONLY if Pillow save fails.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    base = max(sizes_for_check)
    src = render_svg_to_pillow(svg_path, base, base, zoom=zoom, padding=padding, transparent=transparent, bg_color=bg)
    if not transparent:
        src = pillow_flatten(src, qcolor_to_rgba_tuple(bg))

    icns_path = unique_path(out_dir / "icon.icns")
    try:
        src.save(icns_path, format="ICNS")
    except Exception as e:
        if platform.system() == "Darwin":
            iconset = out_dir / "icon.iconset"
            iconset.mkdir(parents=True, exist_ok=True)
            # build from the expected ICNS sizes
            for s in sizes_for_check:
                img = render_svg_to_pillow(svg_path, s, s, zoom=zoom, padding=padding,
                                           transparent=transparent, bg_color=bg)
                img.save(iconset / f"icon_{s}x{s}.png")
            proc = subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(f"ICNS export failed (Pillow + iconutil): {proc.stderr.strip()}") from e
        else:
            # On non-macOS, re-raise original Pillow save error
            raise

def save_png_set(svg_path: str, out_dir: Path, label: str, name: str, sizes: list[int],
                 transparent: bool, zoom: float, padding: int, bg: QColor, fmt: str = "png"):
    """
    Generic PNG/JPG/BMP export set (Linux/Android/iOS). Background baked when needed.
    """
    fmt = fmt.lower()
    base = out_dir / label / name
    base.mkdir(parents=True, exist_ok=True)
    for s in sizes:
        img = render_svg_to_pillow(svg_path, s, s, zoom=zoom, padding=padding,
                                   transparent=transparent, bg_color=bg)
        if fmt in ("jpg", "jpeg", "bmp") or not transparent:
            img = pillow_flatten(img, qcolor_to_rgba_tuple(bg))
        img.save(base / f"{name}_{s}x{s}.{fmt}")

def save_wallpapers(svg_path: str, out_dir: Path, label: str, name: str, sizes: list[QSize],
                    transparent: bool, zoom: float, padding: int, bg: QColor, fmt: str = "png"):
    """
    Wallpapers in PNG/JPG/BMP.
    """
    fmt = fmt.lower()
    base = out_dir / "wallpapers" / label / name
    base.mkdir(parents=True, exist_ok=True)
    for sz in sizes:
        img = render_svg_to_pillow(svg_path, sz.width(), sz.height(), zoom=zoom, padding=padding,
                                   transparent=transparent, bg_color=bg)
        if fmt in ("jpg", "jpeg", "bmp") or not transparent:
            img = pillow_flatten(img, qcolor_to_rgba_tuple(bg))
        img.save(base / f"{name}_{sz.width()}x{sz.height()}.{fmt}")

def save_custom(svg_path: str, out_dir: Path, name: str, w: int, h: int, fmt: str,
                transparent: bool, zoom: float, padding: int, bg: QColor):
    """
    Custom size export honoring PNG/JPG/PDF/BMP.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    img = render_svg_to_pillow(svg_path, w, h, zoom=zoom, padding=padding,
                               transparent=transparent, bg_color=bg)
    fmt = fmt.lower()
    out = unique_path(out_dir / f"{name}_{w}x{h}.{fmt}")
    if fmt == "pdf":
        # PDF has no alpha; ensure opaque
        img = pillow_flatten(img, qcolor_to_rgba_tuple(bg))
        img.convert("RGB").save(out, "PDF")
    else:
        if fmt in ("jpg", "jpeg", "bmp") or not transparent:
            img = pillow_flatten(img, qcolor_to_rgba_tuple(bg))
        img.save(out)


# ---------- GUI ----------
class SvgConverterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SVG/PNG Converter & Icon Generator")
        self.setWindowIcon(QIcon.fromTheme("image-x-svg"))

        self.svg_path: Optional[str] = None
        self.bgColor = QColor("white")

        # Left: Preview
        self.previewLabel = QLabel("Preview")
        self.previewImage = QLabel()
        self.previewImage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previewImage.setMinimumSize(320, 320)
        self.previewImage.setStyleSheet("background:#222; color:#bbb;")

        # Controls
        self.pathLine = QLineEdit(); self.pathLine.setReadOnly(True)
        self.loadBtn = QPushButton("Load SVG/PNG"); self.loadBtn.clicked.connect(self.on_load)

        # Create these BEFORE wiring dynamic handler that uses them
        self.widthSpin = QSpinBox();  self.widthSpin.setRange(16, 16384); self.widthSpin.setValue(1024)
        self.heightSpin = QSpinBox(); self.heightSpin.setRange(16, 16384); self.heightSpin.setValue(1024)

        self.profileCombo = QComboBox()
        self.profileCombo.addItems([
            "Custom export",
            "Create Windows icon (.ico)",
            "Create macOS icon (.icns)",
            "Create Linux icon PNGs",
            "Create Android app icons",
            "Create iOS app icons",
            "Export standard sizes: Computer",
            "Export standard sizes: Phone",
            "Export tablet sizes: Portrait",
            "Export tablet sizes: Landscape",
        ])
        self.profileCombo.currentIndexChanged.connect(self.on_profile_changed)

        self.formatCombo = QComboBox()

        self.paddingSpin = QSpinBox(); self.paddingSpin.setRange(0, 2000); self.paddingSpin.setValue(0)
        self.transparentBg = QCheckBox("Transparent background"); self.transparentBg.setChecked(True)
        self.bgColorBtn = QPushButton("Choose Background Color"); self.bgColorBtn.clicked.connect(self.choose_bg_color)

        # Zoom: only zoom out; start at 100%
        self.zoomSlider = QSlider(Qt.Orientation.Horizontal); self.zoomSlider.setRange(10, 100); self.zoomSlider.setValue(100)
        self.zoomLabel = QLabel("Zoom: 100%")
        self.zoomSlider.valueChanged.connect(lambda v: self.zoomLabel.setText(f"Zoom: {v}%"))

        self.createBtn = QPushButton("Create…"); self.createBtn.setEnabled(False); self.createBtn.clicked.connect(self.on_create)

        # Layouts
        left = QVBoxLayout()
        left.addWidget(self.previewLabel)
        left.addWidget(self.previewImage, 1)

        size_row = QHBoxLayout(); size_row.addWidget(self.widthSpin); size_row.addWidget(QLabel("×")); size_row.addWidget(self.heightSpin)

        form = QFormLayout()
        form.addRow("SVG/PNG:", self.pathLine)
        form.addRow(self.loadBtn)
        form.addRow("Profile:", self.profileCombo)
        form.addRow("Format:", self.formatCombo)
        form.addRow("Size:", size_row)
        form.addRow("Padding:", self.paddingSpin)
        form.addRow(self.transparentBg)
        form.addRow(self.bgColorBtn)
        form.addRow(self.zoomLabel)
        form.addRow(self.zoomSlider)
        form.addRow(self.createBtn)

        root = QHBoxLayout()
        root.addLayout(left, 1)
        root.addLayout(form, 0)
        self.setLayout(root)

        # Signals for live preview
        self.widthSpin.valueChanged.connect(self.update_preview)
        self.heightSpin.valueChanged.connect(self.update_preview)
        self.paddingSpin.valueChanged.connect(self.update_preview)
        self.transparentBg.stateChanged.connect(self.update_preview)
        self.zoomSlider.valueChanged.connect(self.update_preview)

        # Initialize profile-dependent UI after widgets exist
        self.on_profile_changed()

    # ---- UI Actions ----
    def on_profile_changed(self):
        """Dynamically set allowed output formats per profile and toggle size editing."""
        profile = self.profileCombo.currentText()
        self.formatCombo.blockSignals(True)
        self.formatCombo.clear()

        if profile == "Custom export":
            self.formatCombo.addItems(["PNG", "JPG", "PDF", "BMP"])
            self.widthSpin.setEnabled(True)
            self.heightSpin.setEnabled(True)
        elif profile == "Create Windows icon (.ico)":
            self.formatCombo.addItems(["ICO"])
            self.widthSpin.setEnabled(False)
            self.heightSpin.setEnabled(False)
        elif profile == "Create macOS icon (.icns)":
            self.formatCombo.addItems(["ICNS"])
            self.widthSpin.setEnabled(False)
            self.heightSpin.setEnabled(False)
        else:
            # Linux/Android/iOS/Wallpapers → choose raster format; default to PNG
            self.formatCombo.addItems(["PNG", "JPG", "BMP"])
            self.formatCombo.setCurrentText("PNG")
            self.widthSpin.setEnabled(True)
            self.heightSpin.setEnabled(True)

        self.formatCombo.blockSignals(False)
        self.update_preview()

    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Source", "", "SVG or PNG Files (*.svg *.png)")
        if path:
            self.svg_path = path
            self.pathLine.setText(path)
            self.createBtn.setEnabled(True)
            self.update_preview()

    def choose_bg_color(self):
        color = QColorDialog.getColor(self.bgColor, self, "Select Background Color")
        if color.isValid():
            self.bgColor = color
            if self.transparentBg.isChecked():
                QMessageBox.information(self, "Note", "Background color applies when transparency is off.")
            self.update_preview()

    def ask_output_dir(self) -> Optional[str]:
        return QFileDialog.getExistingDirectory(self, "Choose output directory") or None

    # ---- Preview ----
    def update_preview(self):
        if not self.svg_path:
            self.previewImage.setText("No source loaded")
            return

        profile = self.profileCombo.currentText()
        if profile == "Create Windows icon (.ico)":
            w = h = max(WINDOWS_ICO_SIZES)  # 256
        elif profile == "Create macOS icon (.icns)":
            w = h = max(MAC_ICON_SIZES)     # 1024
        else:
            w, h = self.widthSpin.value(), self.heightSpin.value()

        try:
            if self.svg_path.lower().endswith('.png'):
                pil = Image.open(self.svg_path)
                pil = pil.convert("RGBA")
                pil = pil.resize((w, h), LANCZOS_RESAMPLE)
            else:
                pil = render_svg_to_pillow(
                    self.svg_path,
                    width=w, height=h,
                    zoom=self.zoomSlider.value()/100.0,
                    padding=self.paddingSpin.value(),
                    transparent=self.transparentBg.isChecked(),
                    bg_color=self.bgColor
                )
            pix = pillow_to_qpixmap(pil)
            self.previewImage.setPixmap(
                pix.scaled(self.previewImage.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        except Exception as e:
            self.previewImage.setText(f"Preview error:\n{e}")

    # ---- Export ----
    def on_create(self):
        if not self.svg_path:
            QMessageBox.warning(self, "No source", "Please load an SVG or PNG file first.")
            return
        out = self.ask_output_dir()
        if not out:
            return
        out_dir = Path(out)

        profile = self.profileCombo.currentText()
        fmt = self.formatCombo.currentText().lower()
        w, h = self.widthSpin.value(), self.heightSpin.value()
        zoom = self.zoomSlider.value() / 100.0
        padding = self.paddingSpin.value()
        transparent = self.transparentBg.isChecked()
        bg = self.bgColor

        name = Path(self.svg_path).stem

        try:
            def png_render_to_pillow(path, width, height, **kwargs):
                img = Image.open(path)
                img = img.convert("RGBA")
                img = img.resize((width, height), LANCZOS_RESAMPLE)
                return img

            def save_custom_png(src_path, out_dir, name, w, h, fmt, transparent, zoom, padding, bg):
                out_dir.mkdir(parents=True, exist_ok=True)
                img = png_render_to_pillow(src_path, w, h)
                out = unique_path(out_dir / f"{name}_{w}x{h}.{fmt}")
                if fmt == "pdf":
                    img = pillow_flatten(img, qcolor_to_rgba_tuple(bg))
                    img.convert("RGB").save(out, "PDF")
                else:
                    if fmt in ("jpg", "jpeg", "bmp") or not transparent:
                        img = pillow_flatten(img, qcolor_to_rgba_tuple(bg))
                    img.save(out)

            def save_windows_ico_png(src_path, out_dir, sizes, transparent, zoom, padding, bg):
                out_dir.mkdir(parents=True, exist_ok=True)
                base = max(sizes)
                src = png_render_to_pillow(src_path, base, base)
                if not transparent:
                    if src.mode != "RGB":
                        src = src.convert("RGB")
                ico_path = unique_path(out_dir / "icon.ico")
                src.save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])

            def save_macos_icns_png(src_path, out_dir, sizes_for_check, transparent, zoom, padding, bg):
                out_dir.mkdir(parents=True, exist_ok=True)
                base = max(sizes_for_check)
                src = png_render_to_pillow(src_path, base, base)
                if not transparent:
                    src = pillow_flatten(src, qcolor_to_rgba_tuple(bg))
                icns_path = unique_path(out_dir / "icon.icns")
                try:
                    src.save(icns_path, format="ICNS")
                except Exception as e:
                    if platform.system() == "Darwin":
                        iconset = out_dir / "icon.iconset"
                        iconset.mkdir(parents=True, exist_ok=True)
                        for s in sizes_for_check:
                            img = png_render_to_pillow(src_path, s, s)
                            img.save(iconset / f"icon_{s}x{s}.png")
                        proc = subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
                                              capture_output=True, text=True)
                        if proc.returncode != 0:
                            raise RuntimeError(f"ICNS export failed (Pillow + iconutil): {proc.stderr.strip()}") from e
                    else:
                        raise

            def save_png_set_png(src_path, out_dir, label, name, sizes, transparent, zoom, padding, bg, fmt="png"):
                fmt = fmt.lower()
                base = out_dir / label / name
                base.mkdir(parents=True, exist_ok=True)
                for s in sizes:
                    img = png_render_to_pillow(src_path, s, s)
                    if fmt in ("jpg", "jpeg", "bmp") or not transparent:
                        img = pillow_flatten(img, qcolor_to_rgba_tuple(bg))
                    img.save(base / f"{name}_{s}x{s}.{fmt}")

            def save_wallpapers_png(src_path, out_dir, label, name, sizes, transparent, zoom, padding, bg, fmt="png"):
                fmt = fmt.lower()
                base = out_dir / "wallpapers" / label / name
                base.mkdir(parents=True, exist_ok=True)
                for sz in sizes:
                    img = png_render_to_pillow(src_path, sz.width(), sz.height())
                    if fmt in ("jpg", "jpeg", "bmp") or not transparent:
                        img = pillow_flatten(img, qcolor_to_rgba_tuple(bg))
                    img.save(base / f"{name}_{sz.width()}x{sz.height()}.{fmt}")

            if self.svg_path.lower().endswith('.png'):
                if profile == "Custom export":
                    save_custom_png(self.svg_path, out_dir / "custom", name, w, h, fmt, transparent, zoom, padding, bg)
                elif profile == "Create Windows icon (.ico)":
                    save_windows_ico_png(self.svg_path, out_dir / "windows", WINDOWS_ICO_SIZES, transparent, zoom, padding, bg)
                elif profile == "Create macOS icon (.icns)":
                    save_macos_icns_png(self.svg_path, out_dir / "macos", MAC_ICON_SIZES, transparent, zoom, padding, bg)
                elif profile == "Create Linux icon PNGs":
                    save_png_set_png(self.svg_path, out_dir, "linux", name, LINUX_ICON_SIZES, transparent, zoom, padding, bg, fmt)
                elif profile == "Create Android app icons":
                    save_png_set_png(self.svg_path, out_dir, "android", name, ANDROID_ICON_SIZES, transparent, zoom, padding, bg, fmt)
                elif profile == "Create iOS app icons":
                    save_png_set_png(self.svg_path, out_dir, "ios", name, IOS_ICON_SIZES, transparent, zoom, padding, bg, fmt)
                elif profile == "Export standard sizes: Computer":
                    save_wallpapers_png(self.svg_path, out_dir, "desktop", name, DESKTOP_WALLPAPERS, transparent, zoom, padding, bg, fmt)
                elif profile == "Export standard sizes: Phone":
                    save_wallpapers_png(self.svg_path, out_dir, "phone", name, PHONE_WALLPAPERS, transparent, zoom, padding, bg, fmt)
                elif profile == "Export tablet sizes: Portrait":
                    save_wallpapers_png(self.svg_path, out_dir, "tablet_portrait", name, TABLET_PORTRAIT_WALLPAPERS, transparent, zoom, padding, bg, fmt)
                elif profile == "Export tablet sizes: Landscape":
                    save_wallpapers_png(self.svg_path, out_dir, "tablet_landscape", name, TABLET_LANDSCAPE_WALLPAPERS, transparent, zoom, padding, bg, fmt)
                else:
                    QMessageBox.warning(self, "Unsupported", f"Profile '{profile}' is not supported for PNG sources.")
                    return
            else:
                # ...existing code...
                if profile == "Custom export":
                    save_custom(self.svg_path, out_dir / "custom", name, w, h, fmt, transparent, zoom, padding, bg)

                elif profile == "Create Windows icon (.ico)":
                    save_windows_ico(self.svg_path, out_dir / "windows", WINDOWS_ICO_SIZES, transparent, zoom, padding, bg)

                elif profile == "Create macOS icon (.icns)":
                    save_macos_icns(self.svg_path, out_dir / "macos", MAC_ICON_SIZES, transparent, zoom, padding, bg)

                elif profile == "Create Linux icon PNGs":
                    save_png_set(self.svg_path, out_dir, "linux", name, LINUX_ICON_SIZES, transparent, zoom, padding, bg, fmt)

                elif profile == "Create Android app icons":
                    save_png_set(self.svg_path, out_dir, "android", name, ANDROID_ICON_SIZES, transparent, zoom, padding, bg, fmt)

                elif profile == "Create iOS app icons":
                    save_png_set(self.svg_path, out_dir, "ios", name, IOS_ICON_SIZES, transparent, zoom, padding, bg, fmt)

                elif profile == "Export standard sizes: Computer":
                    save_wallpapers(self.svg_path, out_dir, "desktop", name, DESKTOP_WALLPAPERS, transparent, zoom, padding, bg, fmt)

                elif profile == "Export standard sizes: Phone":
                    save_wallpapers(self.svg_path, out_dir, "phone", name, PHONE_WALLPAPERS, transparent, zoom, padding, bg, fmt)

                elif profile == "Export tablet sizes: Portrait":
                    save_wallpapers(self.svg_path, out_dir, "tablet_portrait", name, TABLET_PORTRAIT_WALLPAPERS, transparent, zoom, padding, bg, fmt)

                elif profile == "Export tablet sizes: Landscape":
                    save_wallpapers(self.svg_path, out_dir, "tablet_landscape", name, TABLET_LANDSCAPE_WALLPAPERS, transparent, zoom, padding, bg, fmt)

            QMessageBox.information(self, "Done", f"Export complete to:\n{out_dir}")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ---------- Main ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SvgConverterApp()
    w.resize(900, 520)
    w.show()
    sys.exit(app.exec())
