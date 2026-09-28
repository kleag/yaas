<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/kleag/yaas/main/docs/assets/logo-dark.png">
  <img alt="Yaas" src="https://raw.githubusercontent.com/kleag/yaas/main/docs/assets/logo-light.png" width="300">
</picture>

# Yet Another Audio Splitter

This is Yaas 1.0.0, a desktop application that splits the soundtrack of a
YouTube video into separate stems (vocals, drums, bass, other, ...), for
example to practice an instrument over the rest of the band.

Browse to a video in the built-in browser, click **Start**, and Yaas
downloads its audio, separates it with a machine-learning model, and writes
one WAV file per stem.

Full documentation: **https://kleag.github.io/yaas/**

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/kleag)

## Installation

Ready-to-run builds are on the
[GitHub Releases page](https://github.com/kleag/yaas/releases):

| Platform | Download | ffmpeg |
| --- | --- | --- |
| Windows | `yaas_installer.exe` | Install it separately: `winget install ffmpeg` in PowerShell |
| macOS (Apple Silicon) | `yaas_installer.dmg` | Included |
| Linux (x86_64) | `yaas-x86_64.AppImage` | Install it with your package manager, e.g. `sudo apt install ffmpeg` |

The macOS app isn't signed: the first time, right-click it and choose
**Open** to get past Gatekeeper's warning. On an Intel Mac, install from
PyPI instead.

On any platform with Python 3.12 to 3.14, you can also install from PyPI into
a virtual environment (see the [uv documentation](https://docs.astral.sh/uv/getting-started/)),
with ffmpeg installed separately:

```bash
uv pip install yaas
```

See [Installation](https://kleag.github.io/yaas/installation/) for details,
including GPU acceleration.

## Usage

Start Yaas from your applications menu, or with `yaas` in a terminal when
installed from PyPI. Then:

1. navigate to a YouTube video or playlist in the integrated browser,
2. click **Start** and wait: separation can take a while, especially on CPU,
3. click the stems listed in the status log, or find them in the output
   folder, `$HOME/yaas_tracks` by default.

While a job runs, keep browsing and click **Add to Queue** to split more
videos afterwards. Click **Stop** to stop the running job.

The ☰ menu gives access to:

- **Settings...**: the output folder and the separation model,
- **Open Output Folder**,
- **GPU Acceleration...**: an optional CUDA environment on Windows/Linux, or
  the status of Metal acceleration on Apple Silicon Macs,
- the documentation, the issue tracker, and the version information.

### Separation models

Choose the model in **Settings...**; the choice is kept for future runs.

| Model | Library | Notes |
| --- | --- | --- |
| BS-Roformer (default) | [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) | |
| HTDemucs 6 stems | [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) | Also separates guitar and piano |
| OpenUnmix | [OpenUnmix](https://github.com/sigsep/open-unmix-pytorch) | |

Models are downloaded on first use and cached for later runs.

### Command-line options

These override the settings for a single run:

| Option | Description |
| --- | --- |
| `--version` | Print the version and exit |
| `-o`, `--out DIR` | Output folder |
| `--backend {audio_separator,openunmix}` | Separation library |
| `--model {roformer,htdemucs6s}` | Model used with the `audio_separator` backend |
| `--sample-rate {44100,48000}` | Stems' sample rate |

Please respect the copyright of the videos' authors: if they don't allow
sharing, keep the extracted stems for your personal use.

## Development

Yaas uses [uv](https://docs.astral.sh/uv/). From a clone of the repository:

```bash
uv venv && source .venv/bin/activate
uv pip install -e . --group dev
yaas
pytest
```

Releases are versioned with [bumpver](https://github.com/mbarkhau/bumpver):

```bash
git commit
bumpver update --patch   # or --minor / --major
```

`bumpver` pushes a version tag, which makes GitHub Actions publish the
package to PyPI, and build the Windows, macOS, and Linux packages and attach
them to a GitHub Release. See
[Building & Releasing](https://kleag.github.io/yaas/building/) for building
them locally.

## Author and license

Gaël de Chalendar, aka Kleag
(c) Gaël de Chalendar, 2024-2026

This program is free software, licensed under the Mozilla Public License 2.0
(MPL 2.0) license (see the LICENSE file). It includes most of the
[youtube-to-mp3](https://github.com/cedricouellet/youtube-to-mp3) project,
itself under the MPL license.
