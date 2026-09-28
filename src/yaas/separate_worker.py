"""Track-separation logic, decoupled from the Qt GUI and from PySide6.

This module is imported directly by `yaas.worker.Worker` for the normal,
in-process extraction path, and is also runnable as a standalone script
(`python -m yaas.separate_worker ...`) so it can be invoked as a subprocess
inside a separately provisioned GPU-enabled Python environment (see
`yaas.gpu_env`). Callers pass plain callables for status/progress reporting
instead of Qt signals, so this module has no GUI dependency at all.
"""
import argparse
import contextlib
import importlib
import logging
import os
import sys

import numpy
import soundfile
import soxr
import torch
from openunmix.predict import separate

# Full traceback of a failed audio_separator import, or None. Surfaced in
# the app's status log and by `yaas --self-test`: stderr alone is invisible
# in a packaged app launched from Finder/Explorer/a desktop launcher.
AUDIO_SEPARATOR_IMPORT_ERROR = None
try:
    from audio_separator.separator import Separator
    HAS_AUDIO_SEPARATOR = True
except Exception:
    # Broad except (not just ImportError): a partially-broken frozen build
    # can fail with OSError/RuntimeError/etc. deep in a transitive import
    # too. Print the real cause instead of silently degrading to "not
    # installed" -- that message previously hid two separate packaging bugs
    # (missing soundfile/nodejs_wheel files) behind a generic message.
    import traceback
    AUDIO_SEPARATOR_IMPORT_ERROR = traceback.format_exc()
    print(AUDIO_SEPARATOR_IMPORT_ERROR, file=sys.stderr)
    HAS_AUDIO_SEPARATOR = False


def audio_separator_unavailable_message():
    """User-facing explanation of why audio_separator can't be used, ending
    with the actual exception rather than just "not installed"."""
    cause = (AUDIO_SEPARATOR_IMPORT_ERROR or "").strip().splitlines()
    return ("audio_separator could not be loaded"
            + (f": {cause[-1]}" if cause else "")
            + ". If you installed Yaas with pip, install it with "
            "'pip install \"audio_separator[cpu]\"'; otherwise please report "
            "this error.")

MODEL_MAP = {
    "roformer": "BS-Roformer-SW.ckpt",
    "htdemucs6s": "htdemucs_6s.yaml",
}


def _torch_device():
    """Best available torch device. Unlike audio_separator, OpenUnmix doesn't
    pick one itself: openunmix.predict.separate() runs on CPU unless told
    otherwise, even with a CUDA GPU or on an Apple Silicon Mac (MPS)."""
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def extract_with_openunmix(flac_path, out_dir, status_cb, progress_cb):
    """Returns the paths of the written stems."""
    status_cb(f"Extracting tracks from flac {flac_path} with OpenUnmix...")

    # soundfile rather than torchaudio.load/save: recent torchaudio routes
    # both through torchcodec, which needs FFmpeg's *shared libraries* at
    # runtime. The packaged apps don't have them (the macOS app only bundles
    # the ffmpeg program), whereas soundfile's libsndfile is bundled.
    data, sample_rate = soundfile.read(flac_path, dtype="float32", always_2d=True)
    waveform = torch.from_numpy(data.T)  # (channels, frames), as torchaudio did
    status_cb(f"Loaded audio at {sample_rate} Hz")

    # separate() resamples to the model's own rate (44.1 kHz) from `rate`,
    # so it must be the file's actual rate.
    device = _torch_device()
    status_cb(f"Running OpenUnmix on {device}")
    try:
        estimates = separate(waveform, rate=sample_rate, device=device)
    except (RuntimeError, NotImplementedError) as ex:
        # MPS in particular doesn't implement every op OpenUnmix's STFT and
        # Wiener filtering use, and GPU memory can run out on long tracks.
        if device == "cpu":
            raise
        status_cb(f"OpenUnmix failed on {device} ({ex}); retrying on CPU...")
        estimates = separate(waveform, rate=sample_rate, device="cpu")

    # The estimates are at the model's rate, not necessarily the input's.
    model_rate = 44100
    file_name = os.path.splitext(os.path.basename(flac_path))[0]
    output_files = []
    for source, estimate in estimates.items():
        wav_path = os.path.join(out_dir, f"{file_name}_{source}.wav")
        status_cb(f'Writing {source} to {wav_path}')
        # soundfile wants (frames, channels); estimate is (1, channels, frames).
        soundfile.write(wav_path, estimate[0].to("cpu").numpy().T, model_rate)
        output_files.append(wav_path)
    return output_files


def extract_with_audio_separator(flac_path, out_dir, model_type, status_cb, progress_cb,
                                 model_dir=None):
    """Returns the paths of the written stems."""
    status_cb(f"Extracting tracks from flac {flac_path} with {model_type}...")
    if not HAS_AUDIO_SEPARATOR:
        raise RuntimeError(audio_separator_unavailable_message())

    separator_kwargs = {
        "log_level": logging.INFO,
        "output_dir": out_dir,
        "output_format": "WAV",
    }
    if model_dir:
        # audio_separator's own default (/tmp/audio-separator-models/) isn't
        # a persistent location on most Linux systems (/tmp is commonly
        # wiped on every reboot), which would force a multi-GB model
        # re-download on the next run. Point it at a proper persistent
        # cache directory instead so downloaded models are kept for future
        # extractions, the same way OpenUnmix's models already are (via
        # torch.hub's own persistent ~/.cache).
        os.makedirs(model_dir, exist_ok=True)
        separator_kwargs["model_file_dir"] = model_dir
    separator = Separator(**separator_kwargs)
    _make_model_downloads_atomic(separator)

    model_filename = MODEL_MAP.get(model_type, "BS-Roformer-SW.ckpt")
    # Report the model download (several hundred MB on first use) and the
    # separation itself through progress_cb instead of the ASCII tqdm bars
    # audio_separator draws on the terminal.
    with _redirect_separator_progress(progress_cb, status_cb):
        status_cb(f"Loading model {model_filename} (downloaded on first use)...")
        separator.load_model(model_filename=model_filename)
        status_cb("Separating...")
        output_files = separator.separate(flac_path)

    # Depending on the architecture, these are bare file names in out_dir.
    return [f if os.path.isabs(f) else os.path.join(out_dir, f) for f in output_files]


def resample_wav(path, rate):
    """Resamples the WAV file at path to rate, in place, keeping its sample
    format. The models work at 44.1 kHz, but some DAWs (and 48 kHz
    sessions) would otherwise have to resample every imported stem.
    Returns whether the file was changed."""
    info = soundfile.info(path)
    if info.samplerate == rate:
        return False
    data, _ = soundfile.read(path, dtype="float32", always_2d=True)
    data = soxr.resample(data, info.samplerate, rate, quality="VHQ")
    if info.subtype.startswith("PCM"):
        # Resampling can overshoot full scale a little; integer formats
        # would wrap around rather than clip.
        data = numpy.clip(data, -1.0, 1.0)
    tmp_path = path + ".resampling.wav"
    soundfile.write(tmp_path, data, rate, subtype=info.subtype)
    os.replace(tmp_path, path)
    return True


def _make_model_downloads_atomic(separator):
    """audio_separator only checks that a model file exists before using it,
    so a download interrupted by Stop (which kills this process) would leave
    a truncated model that fails every later run. Download to a .part file
    and only rename it once complete. (OpenUnmix's models come through
    torch.hub, which already does this.)"""
    original = separator.download_file_if_not_exists

    def download_file_if_not_exists(url, output_path):
        if os.path.isfile(output_path):
            return original(url, output_path)
        part_path = output_path + ".part"
        if os.path.exists(part_path):
            os.remove(part_path)
        original(url, part_path)
        os.replace(part_path, output_path)

    separator.download_file_if_not_exists = download_file_if_not_exists


@contextlib.contextmanager
def _redirect_separator_progress(progress_cb, status_cb):
    """Intercept the tqdm progress bars used internally by audio_separator's
    MDX/MDXC/VR/Demucs backends (including the roformer model) and report
    them through progress_cb instead of drawing an ASCII bar on the terminal.
    """
    from tqdm import tqdm as base_tqdm

    devnull = open(os.devnull, "w")

    class _ProgressTqdm(base_tqdm):
        def __init__(self, *args, **kwargs):
            kwargs["file"] = devnull
            super().__init__(*args, **kwargs)

        def display(self, msg=None, pos=None):
            if self.total:
                progress_cb(int(self.n * 100 / self.total))

    class _FakeTqdmModule:
        tqdm = _ProgressTqdm

    # `mdx_separator`/`mdxc_separator`/`vr_separator` do `from tqdm import tqdm`,
    # so the module-level name is the class itself. The demucs modules do
    # `import tqdm` and call `tqdm.tqdm(...)`, so they need a fake module.
    # Each architecture is imported independently and best-effort: some of
    # them pull in heavy optional dependencies (e.g. mdx_separator needs
    # onnx2torch/torchvision) that may not be usable in every environment,
    # and that must not prevent patching (or using) the others.
    module_specs = [
        # Model downloads (download_file_if_not_exists).
        ("audio_separator.separator.separator", "tqdm", lambda m: _ProgressTqdm),
        ("audio_separator.separator.architectures.mdx_separator", "tqdm", lambda m: _ProgressTqdm),
        ("audio_separator.separator.architectures.mdxc_separator", "tqdm", lambda m: _ProgressTqdm),
        ("audio_separator.separator.architectures.vr_separator", "tqdm", lambda m: _ProgressTqdm),
        ("audio_separator.separator.uvr_lib_v5.demucs.apply", "tqdm", lambda m: _FakeTqdmModule),
        ("audio_separator.separator.uvr_lib_v5.demucs.utils", "tqdm", lambda m: _FakeTqdmModule),
    ]
    patches = []
    for module_name, attr, replacement_for in module_specs:
        try:
            mod = importlib.import_module(module_name)
        except Exception as ex:
            # Expected/routine for architectures the current run isn't even
            # using (e.g. mdx_separator failing to import on an environment
            # with a torch/torchvision mismatch is harmless when the actual
            # model in use is MDXC or Demucs) -- this is a debugging detail,
            # not something a user needs to see in the app's status log, so
            # it goes to stderr only rather than through status_cb.
            print(f"Progress bar: skipping {module_name} ({ex.__class__.__name__}: {ex})",
                  file=sys.stderr)
            continue
        patches.append((mod, attr, replacement_for(mod)))
    originals = [(mod, attr, getattr(mod, attr)) for mod, attr, _ in patches]
    for mod, attr, replacement in patches:
        setattr(mod, attr, replacement)
    try:
        yield
    finally:
        for mod, attr, original in originals:
            setattr(mod, attr, original)
        devnull.close()


def extract(flac_path, out_dir, backend, model, status_cb, progress_cb, model_dir=None):
    """Returns the paths of the written stems."""
    if backend == "audio_separator":
        return extract_with_audio_separator(flac_path, out_dir, model, status_cb, progress_cb,
                                            model_dir=model_dir)
    return extract_with_openunmix(flac_path, out_dir, status_cb, progress_cb)


def child_main(conn, flac_path, out_dir, backend, model, model_dir):
    """Entry point of the child process yaas.local_extraction runs the
    separation in. Reports through conn, the write end of a Pipe:
    ("status", str), ("progress", int), then ("done", [stem paths]) or
    ("error", str)."""
    def status_cb(message):
        conn.send(("status", message))

    def progress_cb(value):
        conn.send(("progress", value))

    try:
        output_files = extract(flac_path, out_dir, backend, model,
                               status_cb, progress_cb, model_dir=model_dir)
    except BaseException as ex:
        conn.send(("error", str(ex) or ex.__class__.__name__))
    else:
        conn.send(("done", output_files))
    finally:
        conn.close()


def child_ping(conn):
    """Trivial child process, for `yaas --self-test`: checks that the frozen
    app can start one at all (it needs multiprocessing.freeze_support())."""
    conn.send(("done", [sys.executable]))
    conn.close()


def _cli_main():
    parser = argparse.ArgumentParser(
        description=("Standalone track-separation worker, driven over "
                     "stdout by yaas.gpu_env's subprocess extraction path."))
    parser.add_argument("flac_path")
    parser.add_argument("out_dir")
    parser.add_argument("--backend", default="openunmix",
                        choices=["audio_separator", "openunmix"])
    parser.add_argument("--model", default="roformer",
                        choices=["roformer", "htdemucs6s"])
    parser.add_argument("--model-dir", default=None,
                        help="Persistent directory to cache audio_separator models in.")
    args = parser.parse_args()

    def status_cb(message):
        print(f"YAAS_STATUS {message}", flush=True)

    def progress_cb(value):
        print(f"YAAS_PROGRESS {value}", flush=True)

    try:
        output_files = extract(args.flac_path, args.out_dir, args.backend, args.model,
                               status_cb, progress_cb, model_dir=args.model_dir)
    except BaseException as ex:
        print(f"YAAS_ERROR {ex.__class__.__name__}: {ex}", flush=True)
        return 1
    for path in output_files:
        print(f"YAAS_OUTPUT {path}", flush=True)
    print("YAAS_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
