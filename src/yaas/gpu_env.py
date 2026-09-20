"""Provisioning and lifecycle management for an on-demand, GPU-enabled
extraction environment.

The packaged Windows/macOS/Linux installers bundle CPU-only torch (see
[tool.uv.sources] in pyproject.toml) to stay under GitHub Releases' 2GB
per-asset limit. This module lets a user with an NVIDIA/CUDA GPU opt back
into GPU acceleration from within the app, without redownloading the
installer: it provisions a separate, self-contained Python environment
(via the `uv` binary bundled into the frozen app) with CUDA-capable torch,
and `yaas.worker.Worker` runs extraction there as a subprocess instead of
in-process when it's ready.

NVIDIA CUDA has no macOS equivalent, so this whole feature is Windows/Linux
only; see `is_supported_platform()`.
"""
import os
import shutil
import subprocess
import sys

from . import __version__

GPU_ENV_DIRNAME = "gpu-env"

# torch/torchaudio/torchcodec/torchvision here are deliberately installed
# from the default PyPI index (CUDA-capable), unlike the CPU-only pin used
# for the frozen app's own build (see [tool.uv.sources] in pyproject.toml).
# This is the one place that intentionally opts back into the CUDA wheels.
GPU_PACKAGES = [
    "torch",
    "torchaudio",
    "torchcodec",
    "torchvision",
    "openunmix",
    "audio_separator[gpu]",
]


def is_supported_platform():
    """NVIDIA CUDA doesn't exist on macOS; this feature is Windows/Linux only."""
    return sys.platform != "darwin"


def env_python(env_dir):
    if sys.platform == "win32":
        return os.path.join(env_dir, "Scripts", "python.exe")
    return os.path.join(env_dir, "bin", "python")


def _version_stamp_path(env_dir):
    return os.path.join(env_dir, ".yaas-version")


def find_uv_binary():
    """Locate the `uv` binary bundled into the frozen app. Falls back to a
    system-installed `uv` on PATH, so this also works in dev/source mode
    (not frozen with PyInstaller) without any extra setup."""
    exe_name = "uv.exe" if sys.platform == "win32" else "uv"
    if getattr(sys, "frozen", False):
        candidate = os.path.join(sys._MEIPASS, exe_name)
        if os.path.exists(candidate):
            return candidate
    return shutil.which("uv")


def _separate_worker_script():
    """Path to the standalone separate_worker.py *file* (not the importable
    module) so it can be handed to a different Python interpreter (the GPU
    env's) that doesn't have the `yaas` package installed at all."""
    if getattr(sys, "frozen", False):
        candidate = os.path.join(sys._MEIPASS, "separate_worker.py")
        if os.path.exists(candidate):
            return candidate
    return os.path.join(os.path.dirname(__file__), "separate_worker.py")


def status(env_dir):
    """Returns one of "not_installed", "stale", "ready"."""
    if not os.path.exists(env_python(env_dir)):
        return "not_installed"
    stamp_path = _version_stamp_path(env_dir)
    if not os.path.exists(stamp_path):
        return "stale"
    with open(stamp_path) as f:
        stamped_version = f.read().strip()
    if stamped_version != __version__:
        return "stale"
    return "ready"


def _run_streamed(cmd, status_cb):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line:
            status_cb(line)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed (exit {proc.returncode}): {' '.join(cmd)}")


def check_cuda_available(env_dir):
    result = subprocess.run(
        [env_python(env_dir), "-c", "import torch; print(torch.cuda.is_available())"],
        capture_output=True, text=True, timeout=120)
    return result.returncode == 0 and result.stdout.strip() == "True"


def install(env_dir, status_cb):
    uv = find_uv_binary()
    if not uv:
        raise RuntimeError(
            "The 'uv' tool required to install GPU support was not found "
            "(neither bundled with this build nor available on PATH).")

    if os.path.exists(env_dir):
        status_cb("Removing previous GPU environment...")
        uninstall(env_dir)

    status_cb("Creating an isolated Python environment for GPU acceleration...")
    _run_streamed([uv, "venv", env_dir, "--python", "3.12"], status_cb)

    status_cb("Installing GPU-accelerated PyTorch and separation backends "
              "(this downloads several GB, please be patient)...")
    _run_streamed(
        [uv, "pip", "install", "--python", env_python(env_dir), *GPU_PACKAGES],
        status_cb)

    with open(_version_stamp_path(env_dir), "w") as f:
        f.write(__version__)

    status_cb("Verifying GPU availability...")
    if check_cuda_available(env_dir):
        status_cb("GPU acceleration is ready: a CUDA-capable GPU was detected.")
    else:
        status_cb(
            "Installation finished, but no CUDA-capable GPU was detected on "
            "this machine (or its driver isn't set up). Extraction using "
            "this environment will still work, just on CPU.")


def uninstall(env_dir):
    shutil.rmtree(env_dir, ignore_errors=True)


def run_extraction(env_dir, flac_path, out_dir, backend, model, status_cb, progress_cb,
                   model_dir=None):
    """Runs separate_worker.py as a subprocess inside the GPU env, parsing
    its stdout protocol (YAAS_STATUS/YAAS_PROGRESS/YAAS_ERROR/YAAS_DONE)
    into the same status_cb/progress_cb callbacks the in-process path uses."""
    cmd = [
        env_python(env_dir), _separate_worker_script(),
        flac_path, out_dir, "--backend", backend, "--model", model,
    ]
    if model_dir:
        cmd += ["--model-dir", model_dir]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    error_message = None
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line.startswith("YAAS_STATUS "):
            status_cb(line[len("YAAS_STATUS "):])
        elif line.startswith("YAAS_PROGRESS "):
            progress_cb(int(line[len("YAAS_PROGRESS "):]))
        elif line.startswith("YAAS_ERROR "):
            error_message = line[len("YAAS_ERROR "):]
        elif line == "YAAS_DONE":
            pass
        elif line:
            status_cb(line)
    proc.wait()
    if error_message:
        raise RuntimeError(error_message)
    if proc.returncode != 0:
        raise RuntimeError(f"GPU extraction subprocess exited with code {proc.returncode}")
