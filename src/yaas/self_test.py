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


def _check_bundled_libsndfile():
    # The obsolete PySoundFile package installs a soundfile.py of its own
    # that only looks for a system-wide libsndfile. A Linux desktop usually
    # has one, masking the problem, but a Mac never does, and audio_separator
    # then fails to import. The current soundfile package sets _full_path to
    # its packaged library and only sets _libname when it falls back to a
    # system one.
    import soundfile
    path = getattr(soundfile, "_full_path", None)
    if not path or hasattr(soundfile, "_libname"):
        raise RuntimeError(
            f"soundfile ({soundfile.__file__}) isn't using its packaged "
            f"libsndfile (_soundfile_data), but "
            f"{getattr(soundfile, '_libname', 'a system-wide one')}")
    return path


def _check_tool(name):
    def check():
        path = shutil.which(name)
        if not path:
            raise RuntimeError(f"{name} not found on PATH")
        return path
    return check


def _check_https():
    urllib.request.urlopen("https://www.youtube.com", timeout=30).close()


def _check_soundfile_roundtrip():
    # The OpenUnmix backend reads the FLAC input and writes WAV stems with
    # soundfile (see separate_worker.extract_with_openunmix).
    import numpy
    import soundfile
    with tempfile.TemporaryDirectory() as tmp:
        for ext in ("flac", "wav"):
            path = os.path.join(tmp, f"roundtrip.{ext}")
            soundfile.write(path, numpy.zeros((4410, 2), dtype="float32"), 44100)
            soundfile.read(path)


def run(report_path=None):
    # ffmpeg is bundled only in the macOS app; the Windows installer and the
    # AppImage still rely on a system-wide install, so there it's a warning.
    ffmpeg_required = sys.platform == "darwin"
    checks = [
        ("soundfile uses its bundled libsndfile", _check_bundled_libsndfile, True),
        ("audio_separator import", _check_audio_separator_import, True),
        ("audio_separator architectures", _check_audio_separator_architectures, True),
        ("ffmpeg on PATH", _check_tool("ffmpeg"), ffmpeg_required),
        ("ffprobe on PATH", _check_tool("ffprobe"), ffmpeg_required),
        # Separator() itself refuses to start without ffmpeg, so only a
        # failure despite ffmpeg being there is a packaging bug.
        ("audio_separator Separator()", _check_separator_init,
         ffmpeg_required or bool(shutil.which("ffmpeg"))),
        ("HTTPS certificate verification", _check_https, True),
        ("soundfile FLAC/WAV round trip (OpenUnmix)", _check_soundfile_roundtrip, True),
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
