import os

import numpy
import pytest
import soundfile
import torch

from yaas import separate_worker


def write_tone(path, rate, seconds=1.0, channels=2):
    t = numpy.arange(int(rate * seconds)) / rate
    tone = 0.1 * numpy.sin(2 * numpy.pi * 440 * t)
    soundfile.write(path, numpy.stack([tone] * channels, axis=1).astype("float32"), rate)


def test_openunmix_keeps_stereo_and_passes_the_real_rate(monkeypatch, tmp_path):
    seen = {}

    def fake_separate(audio, rate, device):
        seen["shape"], seen["rate"] = tuple(audio.shape), rate
        frames = int(audio.shape[-1] * 44100 / rate)
        return {"vocals": torch.zeros(1, audio.shape[0], frames),
                "drums": torch.zeros(1, audio.shape[0], frames)}

    monkeypatch.setattr(separate_worker, "separate", fake_separate)
    monkeypatch.setattr(separate_worker, "_torch_device", lambda: "cpu")
    flac = tmp_path / "song.flac"
    write_tone(flac, 48000)

    outputs = separate_worker.extract_with_openunmix(
        str(flac), str(tmp_path), lambda m: None, lambda p: None)

    assert seen == {"shape": (2, 48000), "rate": 48000}
    assert outputs == [str(tmp_path / "song_vocals.wav"), str(tmp_path / "song_drums.wav")]
    info = soundfile.info(outputs[0])
    assert (info.channels, info.samplerate, info.frames) == (2, 44100, 44100)


@pytest.mark.parametrize("subtype", ["PCM_16", "FLOAT"])
def test_resample_wav(tmp_path, subtype):
    path = tmp_path / "stem.wav"
    t = numpy.arange(44100) / 44100
    tone = numpy.sin(2 * numpy.pi * 440 * t)  # full scale: must not wrap
    soundfile.write(path, numpy.stack([tone, -tone], axis=1), 44100, subtype=subtype)

    assert separate_worker.resample_wav(str(path), 48000)

    info = soundfile.info(str(path))
    assert (info.channels, info.samplerate, info.subtype) == (2, 48000, subtype)
    assert abs(info.frames - 48000) <= 1
    data, _ = soundfile.read(str(path))
    assert numpy.abs(data).max() <= 1.0
    assert numpy.allclose(data[:, 0], -data[:, 1], atol=1e-3)
    assert os.listdir(tmp_path) == ["stem.wav"]
    # Already at the right rate: left alone.
    assert not separate_worker.resample_wav(str(path), 48000)


@pytest.mark.skipif(not os.environ.get("YAAS_SLOW_TESTS"),
                    reason="downloads OpenUnmix's model; set YAAS_SLOW_TESTS=1")
def test_openunmix_real_model(tmp_path):
    flac = tmp_path / "song.flac"
    write_tone(flac, 44100, seconds=3)
    outputs = separate_worker.extract_with_openunmix(
        str(flac), str(tmp_path), print, print)
    assert len(outputs) == 4
    for path in outputs:
        assert soundfile.info(path).channels == 2
