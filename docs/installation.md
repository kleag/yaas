# Installation

## Windows: using the installer

If you are on Windows and don't want to deal with Python packaging, grab the
latest `yaas_installer.exe` from the
[GitHub Releases page](https://github.com/kleag/yaas/releases) and run it.

You also need ffmpeg installed. The simplest way on Windows is with winget
(installed by default on Windows 11; available via the Microsoft Store on
older versions). From PowerShell:

```powershell
winget install ffmpeg
```

## macOS: using the installer

Grab the latest `yaas_installer.dmg` from the
[GitHub Releases page](https://github.com/kleag/yaas/releases), open it, and
drag Yaas into `/Applications`.

!!! warning "Unsigned application"
    This build isn't signed or notarized by an Apple Developer account, so
    Gatekeeper will warn that it's from an "unidentified developer" the first
    time you open it. Right-click the app and choose **Open** (instead of
    double-clicking) to bypass that warning once.

You also need ffmpeg, e.g. via [Homebrew](https://brew.sh/):

```bash
brew install ffmpeg
```

## Linux: using the AppImage

Grab the latest `yaas-x86_64.AppImage` from the
[GitHub Releases page](https://github.com/kleag/yaas/releases), make it
executable, and run it:

```bash
chmod +x yaas-x86_64.AppImage
./yaas-x86_64.AppImage
```

Install ffmpeg with your distribution's package manager, e.g. on
Debian/Ubuntu: `sudo apt install ffmpeg`.

## Any platform: using uv / pip

Create and activate a virtual environment. See the
[uv documentation](https://docs.astral.sh/uv/getting-started/) if you're not
familiar with it.

Then install Yaas into that environment:

```bash
uv pip install yaas
```

On Windows, make sure you also have a working Python installation and
ffmpeg installed (see above).
