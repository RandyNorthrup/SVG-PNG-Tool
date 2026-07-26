# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed — three defects in the PNG input path

Found by independent review of the retrofit diff, verified against source, and
fixed only after a regression test for each was confirmed to **fail** against
the pre-fix code.

- **PNG inputs now honour zoom and padding.** The old `png_render_to_pillow`
  resized straight to the target size, silently discarding both controls, so
  the same sliders worked for an SVG input and did nothing for a PNG one.
  Replaced by module-level `render_png_to_pillow`, which mirrors
  `render_svg_to_pillow`'s geometry exactly.
- **Opaque PNG export now uses the chosen background colour.** `convert("RGB")`
  composites onto black; the SVG path only escaped this because the background
  was already baked in upstream. The PNG path now composites onto `bg_color`.
- **macOS `.iconset` filenames now match what `iconutil` accepts.** Both
  writers emitted `icon_<n>x<n>.png` for every configured size, producing
  invalid members like `icon_64x64.png` and `icon_1024x1024.png` — so the
  fallback could fail in exactly the case it exists to cover. New
  `macos_iconset_entries` returns the required base/`@2x` pairs.

### Added — test suite

- 12 tests under `tests/`, run in CI headless via `QT_QPA_PLATFORM=offscreen`.
- Each of the three bug tests was checked against the old code first: exactly
  those three failed, the other nine passed. A regression test that passes on
  broken code proves nothing.

### Added

- Strict quality gate configuration in `pyproject.toml` covering ruff, mypy,
  and bandit. Rules that are disabled carry an inline reason.
- `.pre-commit-config.yaml` and `.github/workflows/quality.yml`, running the
  same gate set locally and in CI.
- `PLAN.md` recording assumptions, resolved decisions, and tracked debt.
- Type annotations on all 23 functions, including Qt slots and the nested
  export helpers inside `on_create`.
- Docstrings on every public function, the main window class, and its slots.
- Development and quality-gate sections in `README.md`.
- `.git-blame-ignore-revs`, so the bulk reformat does not obscure history.

### Changed

- Reformatted with `ruff format`. Verified semantically neutral by AST
  comparison — the only non-whitespace change was added trailing commas.
- Split the combined `import` statement and sorted imports.
- `Optional[X]` replaced with `X | None` under
  `from __future__ import annotations`.
- `subprocess.run` now passes `check=False` explicitly at both call sites. The
  return code was already inspected immediately after; the explicit argument
  documents that `iconutil`'s stderr is deliberately preserved for the error
  message.
- Merged two nested conditionals and removed a redundant assignment before
  `return`.

### Removed

- Unused `os` import (zero usages).
- Unused `**kwargs` parameter from `png_render_to_pillow`. All four call sites
  pass exactly three positional arguments.

### Fixed

- `mypy` configuration targeted Python 3.9, which is below mypy's supported
  floor and caused it to error out. Now 3.10; the application's own runtime
  target is unchanged and still enforced by ruff.

### Notes

Lint findings went from 220 to 0 under the strict configuration, and dead-code
findings from 2 to 0. No behaviour was changed: the GUI was constructed and a
full export run (ICO plus a PNG size set) was executed against a test SVG after
the retrofit.

Two functions, `__init__` and `on_create`, still exceed complexity thresholds.
The relevant rules are ignored for that file only, annotated as deferred rather
than accepted, with the refactor sequence recorded in `PLAN.md`. Splitting a
119-statement export handler with no test suite in place was judged the larger
risk.
