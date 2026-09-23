# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Yaas ("Yet Another Audio Splitter") is a desktop PySide6/Qt GUI app that:
1. embeds a browser (QWebEngineView) so the user can navigate to a YouTube video/playlist,
2. downloads its audio via `pytubefix`, converts it to MP3 then FLAC,
3. splits the FLAC into stems (vocals, drums, bass, other, etc.) using either the OpenUnmix or audio-separator ML backend,
4. writes the resulting WAV stems to an output directory (default `$HOME/yaas_tracks`).

## Commands

Environment uses `uv`. A `.venv` already exists at the repo root.

```bash
# Run the app
yaas
# or, from source without installing:
python -m yaas
# or via the pyinstaller entry point:
python src/pyinstmain.py

# Run with the audio-separator backend (default) or openunmix, and pick a model
yaas --backend audio_separator --model roformer   # or --model htdemucs6s
yaas --backend openunmix
```

Lint (as run in CI, `.github/workflows/python-app.yml`):
```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

There is no test suite in this repo (pytest is installed in CI but no tests exist yet; the "Test with pytest" CI step is commented out).

Packaged builds have a headless smoke test, `yaas --self-test [REPORT_FILE]` (`src/yaas/self_test.py`), which `release.yml` runs on each freshly built installer. Verify packaging fixes with it on a build from a clean venv (not the dev `.venv`):
```bash
uv venv --python 3.12 --seed /tmp/x && uv pip install --python /tmp/x/bin/python . pyinstaller
/tmp/x/bin/pyinstaller yaas.spec && dist/yaas --self-test
```

### Build / release

Versioning is managed by `bumpver`, which keeps `pyproject.toml`, `src/yaas/__init__.py`, `README.md`, and `inno_setup_script.iss` in sync (see `[tool.bumpver]` in `pyproject.toml`). Standard release flow (also documented in README.md):

```bash
git commit
bumpver update --patch   # or --minor / --major
uv build
uv publish
```

Windows packaging (PyInstaller + Inno Setup, driven by `yaas.spec` and `inno_setup_script.iss`, entry point `src/pyinstmain.py`):
```bash
pyinstaller yaas.spec
& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' .\inno_setup_script.iss
```
This is what `.github/workflows/release.yml` runs on `windows-latest` when a version tag is pushed, producing `yaas_installer.exe` and attaching it to a GitHub Release.

## Architecture

Two packages under `src/`:

- **`yaas/`** — the actual GUI application (the entry point declared in `pyproject.toml`'s `[project.scripts]`).
  - `app.py` — `MainWindow` (a `QWidget`): embeds the `QWebEngineView` browser, parses CLI args (`--out`, `--backend`, `--model`), and wires the Start/Stop buttons to a `Worker` thread. `main()` sets Qt platform env vars (forces `xcb` on Linux to avoid Wayland/Chromium bugs) before creating the `QApplication`.
  - `worker.py` — `Worker(QThread)`: runs the whole download→convert→separate pipeline off the UI thread and reports progress via Qt signals (`update_status`, `extraction_done`, `extraction_failed`). `extract_tracks()` dispatches to one of two private methods based on `self.backend_type`:
    - `_extract_with_openunmix` — loads `openunmix.umxl()`, runs `openunmix.predict.separate`, reads/writes audio with `soundfile` (not torchaudio, whose load/save need FFmpeg shared libraries via torchcodec, absent from the packaged apps).
    - `_extract_with_audio_separator` — uses `audio_separator.separator.Separator`; `model_type` (`roformer`/`htdemucs6s`) maps to a checkpoint filename in `model_map`. This import is wrapped in `try/except ImportError` (`HAS_AUDIO_SEPARATOR`) since `audio_separator` is an optional/heavier dependency.
  - `__main__.py` — lets the package run as `python -m yaas`.

- **`yturl2mp3/`** — a small, mostly-standalone library (vendored/adapted from the `youtube-to-mp3` MPL-licensed project, per README) providing the download/convert primitives that `yaas.worker.Worker` reuses directly:
  - `helpers.py` — `download_mp3()` (via `pytubefix`), `convert_mp4_to_mp3()` (via `moviepy`), `is_valid_video_url()` / `is_valid_playlist_url()` (regex validation of YouTube URLs).
  - `config.py` — plain `Config` dataclass-like object (`out_dir`, `timeout`, `max_retries`).
  - `yturl2mp3.py` — a separate standalone CLI (`__main__.py` entry) that does download+convert only, no track separation, no GUI. Not the app's primary entry point; kept as its own tool.

`src/pyinstmain.py` is a thin shim (`import yaas.app; yaas.app.main()`) used as the PyInstaller Analysis entry point in `yaas.spec` instead of `python -m yaas`, since PyInstaller needs a plain script.

### Threading / signal flow

`MainWindow.start_process()` creates a `Worker`, connects its Qt signals to UI slots, and calls `worker.start()` (runs `Worker.run()` on a separate thread). All user-facing status updates go through `self.update_status.emit(...)` inside `Worker`, which is connected to `MainWindow.update_status` — never touch UI widgets directly from `Worker`. `stop_process()` currently calls `QThread.terminate()`, which is an abrupt kill (no graceful cancellation).

### Backend/model selection

CLI args parsed in `MainWindow.parse_args()`: `--backend {audio_separator, openunmix}` (default `audio_separator`) and `--model {roformer, htdemucs6s}` (default `roformer`, only meaningful for the `audio_separator` backend). These are read off `yaas.args` inside `Worker.__init__` via `getattr(..., default)`, so `Worker` degrades gracefully if args are ever missing.
