# PLAN

Quality baseline and tracked debt for SVG-PNG-Tool.

Created 2026-07-26 during a quality retrofit. Records what the gates enforce,
what was deliberately not enforced, and what remains outstanding.

## Current state

| Gate | Command | Status |
|---|---|---|
| Lint | `ruff check .` | passing, 0 findings |
| Format | `ruff format --check .` | passing |
| Types | `mypy svg_converter.py` | 1 known error, see debt |
| Dead code | `vulture svg_converter.py --min-confidence 60` | passing, 0 findings |
| Tests | `pytest tests/ -q` | 12 passing |
| Security | `bandit -c pyproject.toml -r . -ll` | 0 at medium+; 5 low, reviewed |
| Secrets | `gitleaks detect` | clean over full history |
| Dependencies | `pip-audit -r requirements.txt` | see CI |

Retrofit reduced ruff from **220 findings to 0** and vulture from 2 to 0 under
the strict configuration in `pyproject.toml`.

## Assumptions

- Python 3.9+ is the runtime target (`ruff target-version = "py39"`). mypy is
  pinned to 3.10 only because that is the oldest version mypy still supports —
  it does not raise the application's own floor.
- The tool is a single-file desktop application, not an installable library.
  `pyproject.toml` therefore carries tool configuration only, with no
  `[project]` or `[build-system]` table.
- macOS `.icns` export depends on the system `iconutil` binary. There is no
  fallback if it is absent; Pillow's own ICNS writer is tried first.

## Resolved decisions

**Qt-idiom lint rules are disabled, with reasons in `pyproject.toml`.**
`ARG001`/`ARG002`, `FBT001`/`FBT002`/`FBT003`, `PLR0913`/`PLR0917` all fire on
correct PySide6 code: Qt slots receive arguments they need not use, the Qt API
takes positional booleans, and Qt constructors legitimately take many
parameters. Suppressing them removed 113 findings that described the framework,
not defects.

**`subprocess.run(..., check=False)` is explicit at both call sites.** The
return code is inspected immediately afterwards so `iconutil`'s stderr can be
surfaced in the error message. `check=True` would raise `CalledProcessError`
and discard that output.

**Two `except Exception` handlers are kept and annotated.** Both sit in Qt
slots. An exception escaping a slot terminates the application, so a broad
catch that converts failure into a dialog is the correct behaviour, not a
shortcut.

## Debt

### mypy: `Class cannot subclass "QWidget" (has type "Any")`

PySide6 ships incomplete type information, so `QWidget` resolves to `Any` and
strict mode rejects subclassing it. Not a defect in this code.

- Suppressed at the CI step with `continue-on-error`, **not** silenced with a
  blanket `# type: ignore`, so the error stays visible.
- Revisit when PySide6 ships complete stubs or `PySide6-stubs` becomes
  maintained.

### Complexity: `__init__` and `on_create`

| Function | Statements | Branches | Complexity |
|---|---|---|---|
| `SvgConverterApp.__init__` | 69 | — | — |
| `SvgConverterApp.on_create` | 119 | 25 | 43 |

Both exceed the configured thresholds. `C901`, `PLR0912`, and `PLR0915` are
ignored **for this file only**, with a comment marking the ignore as deferred
rather than accepted.

They are long for structural reasons: `__init__` builds the entire Qt widget
tree inline, and `on_create` dispatches across every export profile with a
nested helper defined per profile.

**Why not fixed now:** the extraction is a real refactor, and the project has
no test suite to catch a regression. Splitting a 119-statement export handler
blind is exactly the change that breaks working software.

**Order of work:**
1. Add tests covering each export profile end-to-end.
2. Extract the per-profile helpers out of `on_create` into module-level
   functions — they already mirror the existing top-level `save_*` functions.
3. Split `__init__` into `_build_preview_panel`, `_build_settings_panel`,
   `_wire_signals`.
4. Remove the three ignores from `pyproject.toml`.

### Bandit low-severity findings (5)

`B404`, `B603` ×2, `B607` ×2 — all relate to the `iconutil` subprocess call.

Reviewed and accepted: calls use list form and never `shell=True`, the binary
is a macOS system tool, and the arguments are paths produced by `QFileDialog`
rather than free-text user input. `B603`/`B607` are suppressed in
`pyproject.toml` for this file with that reasoning recorded inline.

Residual risk: `iconutil` is invoked by name, so a hostile entry earlier in
`PATH` could shadow it. This requires an already-compromised machine.

### Pre-existing bugs found during review (not introduced by the retrofit)

An independent review (OpenAI Codex, GPT-5.6-sol) of the retrofit diff
surfaced three genuine defects in the PNG-input export path. All three predate
this work and were verified against the source before being recorded here.

**All three are now fixed** (see CHANGELOG). They were initially deferred for
lack of a regression net; a test suite was added first, each test was confirmed
to fail against the old code, and only then were the fixes applied.

**1. PNG inputs silently ignore zoom and padding.** — FIXED
`png_render_to_pillow` (`svg_converter.py:619`) takes only `path`, `width`,
`height`. Every caller — `save_custom_png`, `save_windows_ico_png`,
`save_macos_icns_png`, `save_png_set_png`, `save_wallpapers_png` — accepts
`zoom` and `padding` parameters and then drops them.

The SVG path honours both via `render_svg_to_pillow`. So the same controls
work for an SVG input and do nothing for a PNG input, with no warning.

**2. PNG-to-ICO ignores the chosen background colour.** — FIXED
`save_windows_ico_png` (`svg_converter.py:658`) handles `transparent=False`
with `src.convert("RGB")`. Pillow composites onto black, not onto `bg`.

The SVG path avoids this because `render_svg_to_pillow` already baked the
background in before the conversion. The PNG path has no such step, so the
user's colour choice is discarded. Correct fix: call
`pillow_flatten(src, qcolor_to_rgba_tuple(bg))`, matching `save_custom_png`.

**3. macOS iconset filenames do not match what `iconutil` expects.** — FIXED
Both `.iconset` writers (`svg_converter.py:276` and `:687`) emit
`icon_<size>x<size>.png` for every entry of `MAC_ICON_SIZES`
(`[16, 32, 64, 128, 256, 512, 1024]`).

`iconutil` requires a fixed set of base and `@2x` pairs — `icon_16x16.png`,
`icon_16x16@2x.png`, `icon_32x32.png`, `icon_32x32@2x.png`, and so on up to
`icon_512x512@2x.png`. `icon_64x64.png` and `icon_1024x1024.png` are not
valid iconset members. The fallback can therefore fail in exactly the
situation it exists to handle — when Pillow's own ICNS writer has already
failed.

### Lint waivers can conceal defects

Bug 1 above is a concrete example worth remembering: suppressing `ARG001`
(unused argument) to quiet Qt-slot noise also silenced the warning that
`zoom` and `padding` were accepted and never used.

The suppression is still correct — `ARG001` fires constantly on legitimate Qt
code — but it is not free. When a rule is disabled wholesale, the defects it
would have caught need another way to surface. Here that was an independent
review.

### Test coverage

12 tests exist (`tests/`), covering the three fixed bugs plus `unique_path`,
`pillow_flatten`, and ICO export. Each bug test was verified to fail against
the pre-fix code before the fix landed — a regression test that passes on
broken code proves nothing.

Still uncovered: the wallpaper and PDF export paths, and `on_create`'s profile
dispatch. Extending coverage there is the prerequisite for the complexity
refactor above.

## Not done

- **Full test coverage** — wallpaper/PDF paths and profile dispatch remain untested.
- **Sanitizers** — not applicable, no native code.
- **Bundle/performance gates** — not applicable, desktop application.
- **Accessibility (Lighthouse)** — not applicable, no web UI.
