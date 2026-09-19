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

import torch
import torchaudio
import openunmix
from openunmix.predict import separate

try:
    from audio_separator.separator import Separator
    HAS_AUDIO_SEPARATOR = True
except ImportError:
    HAS_AUDIO_SEPARATOR = False

MODEL_MAP = {
    "roformer": "BS-Roformer-SW.ckpt",
    "htdemucs6s": "htdemucs_6s.yaml",
}


def extract_with_openunmix(flac_path, out_dir, status_cb, progress_cb):
    status_cb(f"Extracting tracks from flac {flac_path} with OpenUnmix...")
    model = openunmix.umxl()  # noqa: F841 (loaded for its side effect of caching weights)

    waveform, sample_rate = torchaudio.load(flac_path)
    waveform = waveform.mean(dim=0, keepdim=True)  # Convert to mono
    status_cb(f"Loaded audio at: {sample_rate}MHz")

    estimates = separate(waveform, rate=44100)

    for source, estimate in estimates.items():
        file_name = os.path.splitext(os.path.basename(flac_path))[0]
        wav_path = os.path.join(out_dir, f"{file_name}_{source}.wav")
        status_cb(f'Writing result to {wav_path}')
        torchaudio.save(
            wav_path,
            torch.squeeze(estimate).to("cpu"),
            sample_rate=sample_rate,
        )
        status_cb(f'Wrote {source} to {wav_path}')


def extract_with_audio_separator(flac_path, out_dir, model_type, status_cb, progress_cb):
    status_cb(f"Extracting tracks from flac {flac_path} with {model_type}...")
    if not HAS_AUDIO_SEPARATOR:
        raise RuntimeError(
            "audio_separator library not installed. "
            "Please install it with 'pip install \"audio_separator[cpu]\"'")

    separator = Separator(
        log_level=logging.INFO,
        output_dir=out_dir,
        output_format="WAV",
    )

    model_filename = MODEL_MAP.get(model_type, "BS-Roformer-SW.ckpt")
    separator.load_model(model_filename=model_filename)

    # Separate audio, reporting progress through progress_cb instead of the
    # ASCII tqdm bar audio_separator draws on the terminal.
    with _redirect_separator_progress(progress_cb, status_cb):
        output_files = separator.separate(flac_path)

    status_cb(f"Separation complete. Generated files: {output_files}")


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
            status_cb(f"Progress bar: skipping {module_name} ({ex.__class__.__name__}: {ex})")
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
        progress_cb(0)


def extract(flac_path, out_dir, backend, model, status_cb, progress_cb):
    if backend == "audio_separator":
        extract_with_audio_separator(flac_path, out_dir, model, status_cb, progress_cb)
    else:
        extract_with_openunmix(flac_path, out_dir, status_cb, progress_cb)


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
    args = parser.parse_args()

    def status_cb(message):
        print(f"YAAS_STATUS {message}", flush=True)

    def progress_cb(value):
        print(f"YAAS_PROGRESS {value}", flush=True)

    try:
        extract(args.flac_path, args.out_dir, args.backend, args.model,
                status_cb, progress_cb)
    except BaseException as ex:
        print(f"YAAS_ERROR {ex.__class__.__name__}: {ex}", flush=True)
        return 1
    print("YAAS_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
