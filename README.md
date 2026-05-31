# Yet Another Audio Splitter

This is Yaas 0.7.1, a tool to split video soundtracks into separate tracks
using OpenUnmix.

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/kleag)

## Installation

### Using the installer

If you are under Windows and don't know how to use uv and pip (see below), you can use the latest `yaas_installer.exe` in https://github.com/kleag/yaas/releases

You must also install ffmpeg. It seems that the simplest way to do so under Windows is with winget (winget is installed by default on Windows 11, and can be installed using the Windows Store on previous versions).

To install ffmpeg with winget, start PowerShell, and then run:

```
winget install ffmpeg
```

### Using uv

Create and activate a virtual environment. For information on uv, see https://docs.astral.sh/uv/getting-started/.

Then install yaas in your environment:

```bash
uv pip install yaas
```

If you are under Windows, you will have to ensure to have a working python installation and to have ffmpeg installed.

## Usage

### Starting the application

#### When installed with the Windows installer

Search yaas in your installed applications and start it.

#### When installed with uv

Activate your virtual environment and then just run:

```
yaas
```

### Using Yaas

Search the video from which you want to extract the sound tracks using the
integrated browser, click the Start button, wait (it can be long), and then use
the generated audio files. Those are put by default in `$HOME/yaas_tracks`. You
can change the destination dir with the `--out` option.

If you want to interrupt an extraction, just click the `Stop` button that
replaces the `Start` button during work.

Note that you must respect the copyright of the authors. E.g., If they don't
authorize sharing, you must keep your private copy for you.

### Model Options

Yaas supports multiple track separation models:

1. **OpenUnmix** (default): Uses the OpenUnmix model for track separation
2. **Audio Separator**: Uses the audio-separator library with BS-Roformer-SW model

To use the audio-separator model, install it first:
```bash
pip install "audio_separator[cpu]"
```

Then run Yaas with:
```bash
yaas --model audio_separator
```

## Building and distributing

```bash
git commit
bumpver update --patch
uv build
uv publish
```

### Under Windows

```
pyinstaller .\yaas.spec
 & 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' .\inno_setup_script.iss
```

## Author

Gaël de Chalendar, aka Kleag
(c) Gaël de Chalendar, 2024-2026

This program is free software, licensed under the Mozilla Public License 2.0
(MPL 2.0) license (see the LICENSE file). It includes most of the
youtube-to-mp3 project (https://github.com/cedricouellet/youtube-to-mp3),
itself under the MPL license.


