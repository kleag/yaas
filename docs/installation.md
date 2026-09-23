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

!!! note "Apple Silicon only"
    This build is arm64-only (Apple Silicon: M1/M2/M3/...) — GitHub retired
    its free Intel macOS build runners, and no free CI service fills the
    gap. On an Intel Mac, install via `uv pip install yaas` /
    `pip install yaas` instead (see below).

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

## GPU acceleration

The packaged Windows and Linux installers above bundle a CPU-only build of
PyTorch (a CUDA-enabled build alone exceeds GitHub Releases' 2GB per-file
limit), so track separation runs on CPU by default regardless of your
hardware. The macOS installer is different: see
[GPU acceleration on macOS](#gpu-acceleration-on-macos) below.

Installing via `uv pip install yaas` / `pip install yaas` instead pulls the
regular PyPI PyTorch build, which automatically uses a compatible CUDA GPU
when one is available and falls back to CPU otherwise — no configuration
needed.

### Enabling GPU acceleration in the Windows/Linux installers

If you installed Yaas via the Windows or Linux packaged installer and have
an NVIDIA GPU with CUDA support, open the ☰ menu and choose **GPU
Acceleration...**, then **Install**. This downloads a separate, self-contained
Python environment with CUDA-enabled PyTorch (several GB) that Yaas then uses
automatically for extraction whenever it's present. Use the same menu entry
later to check its status, reinstall it (e.g. after upgrading Yaas), or
remove it.

### GPU acceleration on macOS

Apple hardware has no CUDA support, but on Apple Silicon Macs (M1 and later)
Yaas uses the GPU through Apple's Metal (MPS) backend out of the box, with
both the macOS dmg installer and `pip install yaas`. There's nothing extra to
download. The ☰ menu's **GPU Acceleration...** entry shows whether Metal
acceleration is available on your Mac.
