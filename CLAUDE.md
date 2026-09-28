# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Yaas ("Yet Another Audio Splitter") is a desktop PySide6/Qt GUI app that:
1. embeds a browser (QWebEngineView) so the user can navigate to a YouTube video/playlist,
2. downloads its audio via `pytubefix` and decodes it straight to FLAC (no lossy MP3 step),
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

Tests (`tests/`, run by CI after flake8; no network or display needed, `conftest.py` points `HOME`/`XDG_*` at a temp dir and sets `QT_QPA_PLATFORM=offscreen`):
```bash
uv pip install --group dev
pytest
YAAS_SLOW_TESTS=1 pytest   # also runs a real OpenUnmix separation (downloads its model)
```
The pipeline tests replace download/convert/separation with fakes and call `Worker.run()` synchronously; the queue tests drive `JobQueue` with a fake worker factory. `app.py` (QtWebEngine) isn't covered.

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
```

`bumpver` commits, tags and pushes; the tag triggers `publish.yml` (PyPI, via Trusted Publishing — don't also `uv publish` by hand) and `release.yml` (installers). Add the release's notes to `docs/changelog.md`.

Windows packaging (PyInstaller + Inno Setup, driven by `yaas.spec` and `inno_setup_script.iss`, entry point `src/pyinstmain.py`):
```bash
pyinstaller yaas.spec
& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' .\inno_setup_script.iss
```
This is what `.github/workflows/release.yml` runs on `windows-latest` when a version tag is pushed, producing `yaas_installer.exe` and attaching it to a GitHub Release.

## Architecture

Two packages under `src/`:

- **`yaas/`** — the actual GUI application (the entry point declared in `pyproject.toml`'s `[project.scripts]`).
  - `app.py` — `MainWindow` (a `QWidget`): embeds the `QWebEngineView` browser, shows the job list and status log (a `QTextBrowser`, with clickable links to the written stems), and forwards Start/Stop to a `JobQueue`. `parse_args()` (`--out`, `--backend`, `--model`, `--sample-rate`, `--version`) runs in `main()` before the `QApplication` exists; `main()` also sets Qt platform env vars (forces `xcb` on Linux to avoid Wayland/Chromium bugs).
  - `jobs.py` — `Job` (URL + the output dir/backend/model it was queued with) and `JobQueue(QObject)`: runs queued jobs one at a time, in order, one `Worker` each; widget-free so it's testable.
  - `worker.py` — `Worker(QThread)`: runs one job (a video, or each video of a playlist) through download→FLAC→separate off the UI thread, in a per-job temp folder under `<AppData>/work` (removed at the end; stale ones cleaned at startup). Signals: `update_status`, `progress` (-1 = indeterminate), `job_finished(state, message)` with state `DONE`/`FAILED`/`CANCELLED`; written stems end up in `worker.outputs`. Separation always runs in a child process: the GPU env's (`gpu_env.run_extraction`) when it's ready, else `local_extraction.run_extraction`.
  - `separate_worker.py` — the separation itself, free of Qt (status/progress are plain callbacks), also runnable as a script inside the GPU env:
    - `extract_with_openunmix` — runs `openunmix.predict.separate` on the stereo audio at its real sample rate, reads/writes audio with `soundfile` (not torchaudio, whose load/save need FFmpeg shared libraries via torchcodec, absent from the packaged apps).
    - `extract_with_audio_separator` — uses `audio_separator.separator.Separator`; `model_type` (`roformer`/`htdemucs6s`) maps to a checkpoint filename in `MODEL_MAP`. The import is guarded (`HAS_AUDIO_SEPARATOR`, `AUDIO_SEPARATOR_IMPORT_ERROR`). `_redirect_separator_progress` swaps audio_separator's tqdm bars (model download and separation) for `progress_cb`.
    - Both return the written stems' paths.
    - `resample_wav` — resamples a stem in place, keeping its sample format.
  - `local_extraction.py` — runs `separate_worker.child_main` in a `multiprocessing` "spawn" child (never fork: the parent is multi-threaded Qt), reporting over a `Pipe`, so Stop can kill it mid-computation. In the frozen app the child is the app executable itself: `multiprocessing.freeze_support()` (in `pyinstmain.py` and `app.main()`) must run first, and entry modules must keep their `if __name__ == "__main__"` guards (spawn re-imports the main module). `yaas --self-test` checks the child can start.
  - `gpu_env.py` — the optional CUDA environment (Windows/Linux): installs torch from PyTorch's CUDA index (`cu126`, or `cu130` for Blackwell per `nvidia-smi`; PyPI's Windows torch is CPU-only), then the backends from PyPI; `run_extraction` speaks a `YAAS_STATUS`/`YAAS_PROGRESS`/`YAAS_OUTPUT`/`YAAS_ERROR`/`YAAS_DONE` stdout protocol with `separate_worker.py`.
  - `settings.py` — `yaas.conf` (QSettings INI): output dir, model, and stems sample rate (48 kHz by default; the models work at 44.1 kHz, so `Worker` resamples the written stems in-process with `separate_worker.resample_wav`, via soxr).
  - `__main__.py` — lets the package run as `python -m yaas`.

- **`yturl2mp3/`** — a small, mostly-standalone library (vendored/adapted from the `youtube-to-mp3` MPL-licensed project, per README) providing the download/convert primitives that `yaas.worker.Worker` reuses directly:
  - `helpers.py` — `download_audio()` (via `pytubefix`), `convert_to_flac()` / `convert_mp4_to_mp3()` (via `pydub`), `is_valid_video_url()` / `is_valid_playlist_url()` (regex validation of YouTube URLs: watch, shorts, live, youtu.be, m./music. hosts, playlists).
  - `config.py` — plain `Config` dataclass-like object (`out_dir`, `timeout`, `max_retries`).
  - `yturl2mp3.py` — a separate standalone CLI (`__main__.py` entry) that does download+convert only, no track separation, no GUI. Not the app's primary entry point; kept as its own tool.

`src/pyinstmain.py` is a thin shim (`import yaas.app; yaas.app.main()`) used as the PyInstaller Analysis entry point in `yaas.spec` instead of `python -m yaas`, since PyInstaller needs a plain script.

### Threading / signal flow

`MainWindow.start_process()` adds a `Job` to the `JobQueue`, which creates the `Worker`, connects its signals to its own (queued connections, delivered on the UI thread) and starts it; the next job starts on the worker's `QThread.finished`. Never touch UI widgets from `Worker`. Stopping: `Worker.cancel()` kills the separation's child process (handed over through `on_start`), and sets a flag checked between steps and in the status/progress callbacks (which then raise `Cancelled`, e.g. to stop a download). Only the short FLAC conversion isn't interruptible. `separate_worker` makes audio_separator's model downloads atomic (`.part` then rename), since a kill can land mid-download. Never use `QThread.terminate()`. `MainWindow.closeEvent` stops the queue and `os._exit`s if a thread won't stop in time (Qt aborts when a running `QThread` is destroyed).

### Backend/model selection

The model is chosen in the Settings dialog (a combo box over `settings.MODELS`, which maps each choice to a backend + model pair) and persisted in `yaas.conf`; `MainWindow.apply_model_setting()` copies it into `self.args.backend`/`self.args.model`. The CLI args `--backend {audio_separator, openunmix}` and `--model {roformer, htdemucs6s}` (default `None`) override it for one run only, like `--out` and `--sample-rate`; if only one is given, the other falls back to `audio_separator`/`roformer`. OpenUnmix has no model choice: its model is `None`. Each `Job` captures the backend/model when queued.
