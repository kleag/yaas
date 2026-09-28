import subprocess
import sys
import textwrap

import pytest

from yaas import gpu_env


@pytest.fixture
def fake_worker_script(monkeypatch, tmp_path):
    """Makes run_extraction run the given code with this Python instead of
    the GPU environment's separate_worker.py."""
    def install(code):
        script = tmp_path / "fake_worker.py"
        script.write_text(textwrap.dedent(code))
        monkeypatch.setattr(gpu_env, "env_python", lambda env_dir: sys.executable)
        monkeypatch.setattr(gpu_env, "_separate_worker_script", lambda: str(script))
    return install


def test_run_extraction_protocol(fake_worker_script):
    fake_worker_script("""
        import sys
        print("YAAS_STATUS args " + " ".join(sys.argv[1:]))
        print("YAAS_PROGRESS 40")
        print("some library log line")
        print("YAAS_OUTPUT /out/song_vocals.wav")
        print("YAAS_OUTPUT /out/song_drums.wav")
        print("YAAS_DONE")
    """)
    statuses, progress = [], []
    outputs = gpu_env.run_extraction("env", "song.flac", "/out", "openunmix", None,
                                     statuses.append, progress.append)
    assert outputs == ["/out/song_vocals.wav", "/out/song_drums.wav"]
    assert progress == [40]
    # No --model for OpenUnmix.
    assert statuses == ["args song.flac /out --backend openunmix",
                        "some library log line"]


def test_run_extraction_error(fake_worker_script):
    fake_worker_script("""
        print("YAAS_ERROR ValueError: bad file")
        raise SystemExit(1)
    """)
    with pytest.raises(RuntimeError, match="ValueError: bad file"):
        gpu_env.run_extraction("env", "song.flac", "/out", "audio_separator",
                               "roformer", print, print)


def test_run_extraction_can_be_killed(fake_worker_script):
    fake_worker_script("""
        import time
        print("YAAS_STATUS started", flush=True)
        time.sleep(60)
    """)

    def on_start(proc):
        proc.terminate()

    with pytest.raises(RuntimeError, match="exited with code"):
        gpu_env.run_extraction("env", "song.flac", "/out", "openunmix", None,
                               print, print, on_start=on_start)


@pytest.mark.parametrize("nvidia_smi_output, variant", [
    ("8.6\n", "cu126"),
    ("7.5\n12.0\n", "cu130"),
    ("10.0\n", "cu130"),
    ("", "cu126"),
])
def test_cuda_wheel_variant(monkeypatch, nvidia_smi_output, variant):
    monkeypatch.setattr(
        gpu_env.subprocess, "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0, stdout=nvidia_smi_output))
    assert gpu_env.cuda_wheel_variant() == variant


def test_cuda_wheel_variant_without_nvidia_smi(monkeypatch):
    def run(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")
    monkeypatch.setattr(gpu_env.subprocess, "run", run)
    assert gpu_env.cuda_wheel_variant() == "cu126"


def test_install_takes_torch_from_the_cuda_index(monkeypatch, tmp_path):
    commands = []
    env_dir = tmp_path / "gpu-env"

    def run_streamed(cmd, status_cb):
        commands.append(cmd)
        env_dir.mkdir(exist_ok=True)

    monkeypatch.setattr(gpu_env, "find_uv_binary", lambda: "uv")
    monkeypatch.setattr(gpu_env, "_run_streamed", run_streamed)
    monkeypatch.setattr(gpu_env, "cuda_wheel_variant", lambda: "cu126")
    monkeypatch.setattr(gpu_env, "check_cuda_available", lambda env_dir: True)

    gpu_env.install(str(env_dir), lambda message: None)

    venv, torch_install, backends_install = commands
    assert venv[:2] == ["uv", "venv"]
    assert "https://download.pytorch.org/whl/cu126" in torch_install
    assert set(gpu_env.TORCH_PACKAGES) <= set(torch_install)
    assert "--index-url" not in backends_install
    assert set(gpu_env.BACKEND_PACKAGES) <= set(backends_install)
    assert gpu_env.status(str(env_dir)) in ("ready", "not_installed")
