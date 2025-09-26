# SVG Converter & Icon Generator (CairoSVG Backend)

## Overview

The **SVG Converter & Icon Generator** is a cross-platform desktop tool
built with **PySide6**, **CairoSVG**, and **Pillow** that converts SVG
files into multiple raster formats, app icons, and wallpapers with
flexible export profiles.

This tool supports generating: - **Windows ICO** icons (multi-size) -
**macOS ICNS** icons with optional `iconutil` fallback - **Linux,
Android, iOS PNG icon sets** - **Custom exports** (PNG, JPG, BMP, PDF) -
**Wallpapers** for multiple devices and orientations

## Features

-   **SVG → PNG/JPG/BMP/PDF** conversion via **CairoSVG**\
-   **App icons** for Windows (.ico) and macOS (.icns) with multiple
    sizes\
-   **Linux / Android / iOS** platform icon sets\
-   **Dynamic format dropdowns** depending on export profile\
-   **Zoom control** (100% default, only zoom out to fit)\
-   **Transparent or colored background** toggle\
-   **Live preview** before export\
-   **Automatic multi-size ICO/ICNS packaging**\
-   **Cross-platform GUI** built with PySide6

## Requirements

Install dependencies with:

``` bash
pip install PySide6 Pillow cairosvg
```

macOS users exporting **ICNS** should also have `iconutil` available
(preinstalled on macOS).

## Usage

1.  Launch the app:

    ``` bash
    python svg_converter.py
    ```

2.  Load an **SVG file**.

3.  Choose an **export profile** (e.g., Windows ICO, macOS ICNS, Linux
    icons, wallpapers).

4.  Select **format**, **background**, and **zoom level**.

5.  Click **Create** → Choose output folder → Files are exported
    automatically.

## Export Profiles

  ------------------------------------------------------------------------
  Profile                Output Format(s)    Notes
  ---------------------- ------------------- -----------------------------
  Custom Export          PNG, JPG, BMP, PDF  Single size export

  Windows Icon (.ico)    ICO (multi-size)    Sizes: 16--256 px

  macOS Icon (.icns)     ICNS (multi-size)   Sizes: 16--1024 px, alpha or
                                             fallback

  Linux Icon PNGs        PNG/JPG/BMP         Standard icon sizes

  Android App Icons      PNG/JPG/BMP         Google Play icon sizes

  iOS App Icons          PNG/JPG/BMP         iOS icon sizes

  Wallpapers (Desktop,   PNG/JPG/BMP         Multiple resolutions
  Phone...)                                  
  ------------------------------------------------------------------------

## Zoom Behavior

-   **100%** → Fit inside width × height minus padding.\
-   **\<100%** → Shrinks proportionally.\
-   **Never overscales** beyond original fit size.

## Background Options

-   **Transparent background** → Alpha channel retained for PNG/ICNS.\
-   **Color background** → Applied when transparency is disabled or for
    formats without alpha (JPG, BMP, PDF).

## Platform Notes

-   **Windows ICO** → Single `.ico` with all selected sizes.
-   **macOS ICNS** → Pillow direct ICNS export, with optional `iconutil`
    fallback on macOS.
-   **Linux/Android/iOS** → Multiple PNG/JPG/BMP files in platform
    folders.

## License

MIT License -- free to use and modify.

## Author

Randy Northrup
