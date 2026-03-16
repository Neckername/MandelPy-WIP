# Security Best Practices Review - MandelPy

Date: 2026-03-16
Reviewer: Codex security-best-practices skill

## Scope and Method

- Reviewed first-party source files: `main.py`, `core/*.py`, `ui/*.py`, `requirements.txt`, `MandelPy.spec`, `MandelPy Installer.iss`.
- Excluded generated or bundled third-party trees (`dist/`, `build/`, `resources_rc.py`) to avoid false positives from vendored dependencies.
- Project stack is Python + PySide6 desktop application. No framework-specific guidance file in the skill references directly matches this stack (no first-party Flask/FastAPI/Django server code), so Python secure-by-default guidance was applied.

## Executive Summary

No direct remote code execution, command injection, or embedded secret material was found in first-party code. The most important gaps are local file trust boundaries: preset filenames can escape the intended directory, imported preset files are not validated before parsing/display, and preferences are accepted with minimal schema validation. Dependency hygiene can also be tightened to reduce supply-chain exposure.

## Findings

### Medium Severity

#### SBP-001 - Preset name path traversal can write outside `ASSETS_DIR`
- Locations:
  - `core/gradient.py:38-41`
  - `ui/dialogs.py:241-250`
  - `ui/dialogs.py:400-417`
- Evidence:
  - User-provided `name` / `new_name` is interpolated directly into `ASSETS_DIR / f"{name}.grd"` and then written/renamed.
  - No normalization or rejection of separators (`/`, `\\`) or traversal segments (`..`).
- Risk:
  - A crafted preset name can target unintended paths writable by the current user, causing arbitrary file overwrite/move in user context.
- Secure-by-default improvement:
  - Validate names against a strict allowlist (for example `^[A-Za-z0-9 _.-]{1,64}$`).
  - Resolve and enforce path containment (`candidate.resolve().parent == ASSETS_DIR.resolve()`).
  - Reject absolute paths, traversal segments, reserved names, and separator characters.

#### SBP-002 - Imported preset files are parsed without size/schema validation
- Locations:
  - `ui/dialogs.py:342-355`
  - `ui/dialogs.py:371-385`
  - `core/gradient.py:43-45`
- Evidence:
  - Any selected `.grd` file is copied, then loaded with `json.loads(path.read_text(...))`.
  - `refresh()` and `apply_selected()` do not wrap parsing/validation errors.
  - No file size cap or schema checks before use.
- Risk:
  - Malformed or oversized files can crash dialogs or freeze the app (availability/DoS via untrusted local content).
- Secure-by-default improvement:
  - Enforce a maximum preset file size (for example 1 MiB).
  - Wrap parsing in `try/except` and quarantine/skip invalid presets.
  - Validate schema (`name` as bounded string; `stops` list length bounds; each stop has float `0..1` and valid color string).

### Low Severity

#### SBP-003 - Preferences are loaded with minimal validation and broad trust
- Locations:
  - `core/prefs.py:57-65`
  - `ui/mainwindow.py:92-100`
- Evidence:
  - `load_prefs()` accepts almost all JSON values as-is and only repairs `gradient` length.
  - Trusted values directly influence rendering and filesystem writes (for example `default_save`, iteration settings).
- Risk:
  - Tampered preference files can trigger unstable behavior or heavy resource use.
- Secure-by-default improvement:
  - Add a strict preference schema with typed defaults and range clamping.
  - Canonicalize and validate `default_save` path before writing.
  - On invalid fields, reset only invalid keys instead of trusting whole object.

#### SBP-004 - Runtime dependency set is broader than needed
- Locations:
  - `requirements.txt:1-36`
- Evidence:
  - Runtime list includes web/server and test/build-related packages (for example `Flask`, `Jinja2`, `Werkzeug`, `pytest`, `pyinstaller`) that are not imported by reviewed first-party runtime modules.
- Risk:
  - Larger supply-chain attack surface and patching burden.
- Secure-by-default improvement:
  - Split dependencies into `requirements-runtime.txt`, `requirements-dev.txt`, and build-only requirements.
  - Keep runtime minimal.
  - Prefer hash-pinned installs (`pip-compile --generate-hashes` or equivalent).

## Prioritized Remediation Plan

1. Fix preset filename/path traversal (SBP-001).
2. Add robust preset import validation with size/schema checks and error handling (SBP-002).
3. Add strict preference schema validation/clamping (SBP-003).
4. Minimize and separate runtime vs dev/build dependencies (SBP-004).

## Notes

- No evidence of first-party `eval`, `exec`, unsafe deserialization, subprocess shell execution, or hardcoded credentials was found in reviewed first-party files.
- A full dependency CVE audit was not executed in this run.
