"""`yaas --self-test [REPORT_FILE]`: smoke-test a packaged (PyInstaller)
build without opening any window.

Every packaging bug so far has had the same shape: it works from a pip
install, but the frozen app is missing a data file, a library, some package
metadata or a CA bundle, and the user only finds out mid-extraction, behind
a generic error message. release.yml runs this on each freshly built
installer, so such a build fails CI with the real traceback instead of
reaching users.

The report goes to REPORT_FILE (when given) as well as stdout: a windowed
Windows build has no usable stdout at all.
"""
import os
import shutil
import sys
import tempfile
import traceback
import urllib.request

from . import __version__
from . import separate_worker

AUDIO_SEPARATOR_ARCHITECTURES = [
    "audio_separator.separator.architectures.mdx_separator",
    "audio_separator.separator.architectures.mdxc_separator",
    "audio_separator.separator.architectures.vr_separator",
    "audio_separator.separator.architectures.demucs_separator",
]


def _check_audio_separator_import():
    if not separate_worker.HAS_AUDIO_SEPARATOR:
        raise RuntimeError(separate_worker.AUDIO_SEPARATOR_IMPORT_ERROR)


def _check_audio_separator_architectures():
    # Imported dynamically by name at model-load time (see yaas.spec), so a
    # plain import of audio_separator doesn't prove they're bundled.
    import importlib
    for name in AUDIO_SEPARATOR_ARCHITECTURES:
        importlib.import_module(name)


def _check_separator_init():
    # Runs audio_separator's own environment checks (ffmpeg, package
    # metadata, torch/onnxruntime device setup) without downloading a model.
    import logging
    with tempfile.TemporaryDirectory() as tmp:
        separate_worker.Separator(log_level=logging.WARNING, output_dir=tmp,
                                  model_file_dir=tmp)


def _check_tool(name):
    def check():
        path = shutil.which(name)
        if not path:
            raise RuntimeError(f"{name} not found on PATH")
        return path
    return check


def _check_https():
    urllib.request.urlopen("https://www.youtube.com", timeout=30).close()


def _check_torchaudio_roundtrip():
    # OpenUnmix backend: recent torchaudio load/save go through torchcodec,
    # which needs FFmpeg's shared libraries, not just the ffmpeg program.
    import torch
    import torchaudio
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "roundtrip.wav")
        torchaudio.save(path, torch.zeros(1, 4410), sample_rate=44100)
        torchaudio.load(path)


def run(report_path=None):
    # ffmpeg is bundled only in the macOS app; the Windows installer and the
    # AppImage still rely on a system-wide install, so there it's a warning.
    ffmpeg_required = sys.platform == "darwin"
    checks = [
        ("audio_separator import", _check_audio_separator_import, True),
        ("audio_separator architectures", _check_audio_separator_architectures, True),
        ("ffmpeg on PATH", _check_tool("ffmpeg"), ffmpeg_required),
        ("ffprobe on PATH", _check_tool("ffprobe"), ffmpeg_required),
        # Separator() itself refuses to start without ffmpeg, so only a
        # failure despite ffmpeg being there is a packaging bug.
        ("audio_separator Separator()", _check_separator_init,
         ffmpeg_required or bool(shutil.which("ffmpeg"))),
        ("HTTPS certificate verification", _check_https, True),
        ("torchaudio save/load (OpenUnmix)", _check_torchaudio_roundtrip, False),
    ]
    lines = [f"Yaas {__version__} self-test ({sys.platform}, "
             f"frozen={getattr(sys, 'frozen', False)})"]
    failed = 0
    for name, check, required in checks:
        try:
            result = check()
            lines.append(f"PASS  {name}" + (f": {result}" if result else ""))
        except BaseException:
            tag = "FAIL" if required else "WARN"
            failed += required
            lines.append(f"{tag}  {name}\n{traceback.format_exc()}")
    lines.append("Self-test " + ("FAILED" if failed else "passed"))
    report = "\n".join(lines) + "\n"

    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
    if sys.stdout is not None:
        sys.stdout.write(report)
        sys.stdout.flush()
    return 1 if failed else 0
