# Usage

## Starting the application

### Installed with the Windows installer

Search for "Yaas" in your installed applications and start it.

### Installed with the macOS installer or the Linux AppImage

Launch it like any other application (from `/Applications` on macOS, or by
running the `.AppImage` file on Linux).

### Installed with uv / pip

Activate your virtual environment and run:

```bash
yaas
```

## Extracting stems

1. Use the embedded browser to search for or navigate to the video you want.
2. Click **Start**.
3. Wait — separation can take a while, especially on CPU.
4. Find the resulting stems in the output directory (`$HOME/yaas_tracks` by
   default; override with `--out`).

If you want to interrupt an extraction, click **Stop**, which replaces
**Start** while a job is running.

!!! note
    Respect the copyright of the video's authors. If they don't authorize
    sharing, keep your extracted stems for personal use only.

## The menu

The ☰ button in the top-left corner opens a menu with:

- **Documentation** — opens this site in your browser.
- **Report an Issue** — opens the GitHub issue tracker.
- **GPU Acceleration...** (Windows/Linux only) — install, reinstall, or
  remove an on-demand CUDA-accelerated environment; see
  [Installation](installation.md#enabling-gpu-acceleration-in-the-windowslinux-installers).
- **About Yaas** — shows the installed version and license.

## Choosing a separation backend

Yaas supports two backends for splitting the soundtrack into stems:

1. **audio-separator** (default) — uses the
   [audio-separator](https://github.com/nomadkaraoke/python-audio-separator)
   library. Choose a model with `--model`:
      - `roformer` (default)
      - `htdemucs6s`
2. **OpenUnmix** — uses the
   [OpenUnmix](https://github.com/sigsep/open-unmix-pytorch) model.

```bash
# Default backend and model
yaas

# audio-separator with a specific model
yaas --backend audio_separator --model htdemucs6s

# OpenUnmix backend
yaas --backend openunmix
```

## Command-line options

| Option | Default | Description |
| --- | --- | --- |
| `-o`, `--out DIR` | `$HOME/yaas_tracks` | Directory to store the output files in. |
| `--backend {audio_separator,openunmix}` | `audio_separator` | Track separation backend. |
| `--model {roformer,htdemucs6s}` | `roformer` | Model used by the `audio_separator` backend. |
