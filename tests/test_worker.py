"""Worker's pipeline, with the download, conversion and separation steps
replaced by fakes. run() is called directly, on the test's thread."""
import os

import pytest

from yaas import worker as worker_module
from yaas.worker import CANCELLED, DONE, FAILED, Worker, work_root

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL123"


class FakeYouTube:
    def __init__(self, url, client=None, on_progress_callback=None):
        self.url = url
        self.on_progress = on_progress_callback


class FakePlaylist:
    urls = []

    def __init__(self, url):
        self.video_urls = list(self.urls)


@pytest.fixture
def pipeline(monkeypatch, qapp):
    """Fakes every pipeline step; tests tweak `calls`/`fail`/`on_extract`."""
    state = {"fail": set(), "on_extract": None, "extracted": []}

    def download_audio(video, config):
        if video.url in state["fail"]:
            raise RuntimeError(f"download of {video.url} failed")
        video.on_progress(type("S", (), {"filesize": 10})(), b"", 0)
        path = os.path.join(config.out_dir, video.url[-11:] + ".m4a")
        open(path, "w").close()
        return path

    def convert_to_flac(path, flac_path):
        open(flac_path, "w").close()
        return flac_path

    def run_extraction(flac_path, out_dir, backend, model, status_cb, progress_cb,
                       model_dir=None, on_start=None):
        state["extracted"].append(flac_path)
        if state["on_extract"]:
            state["on_extract"](status_cb, progress_cb)
        stem = os.path.join(out_dir, os.path.basename(flac_path) + "_vocals.wav")
        open(stem, "w").close()
        return [stem]

    monkeypatch.setattr(worker_module, "YouTube", FakeYouTube)
    monkeypatch.setattr(worker_module, "Playlist", FakePlaylist)
    monkeypatch.setattr(worker_module, "download_audio", download_audio)
    monkeypatch.setattr(worker_module, "convert_to_flac", convert_to_flac)
    monkeypatch.setattr(worker_module.local_extraction, "run_extraction", run_extraction)
    monkeypatch.setattr(worker_module.gpu_env, "status", lambda env_dir: "not_installed")
    return state


def run_worker(url, out_dir, backend="openunmix", model=None):
    worker = Worker(url, str(out_dir), backend, model)
    results, statuses = [], []
    worker.job_finished.connect(lambda state, message: results.append((state, message)))
    worker.update_status.connect(statuses.append)
    worker.run()
    assert len(results) == 1
    return worker, results[0], statuses


def work_dirs():
    return os.listdir(work_root()) if os.path.isdir(work_root()) else []


def test_single_video(pipeline, tmp_path):
    worker, (state, message), _ = run_worker(VIDEO_URL, tmp_path / "out")
    assert state == DONE and message == ""
    assert worker.outputs == [str(tmp_path / "out" / "dQw4w9WgXcQ.flac_vocals.wav")]
    assert os.path.exists(worker.outputs[0])
    assert work_dirs() == []  # intermediate files removed


def test_invalid_url(pipeline, tmp_path):
    _, (state, message), _ = run_worker("https://www.youtube.com/", tmp_path)
    assert state == FAILED
    assert "Not a YouTube video or playlist URL" in message


def test_extraction_failure(pipeline, tmp_path):
    def fail(status_cb, progress_cb):
        raise RuntimeError("out of memory")
    pipeline["on_extract"] = fail
    worker, (state, message), _ = run_worker(VIDEO_URL, tmp_path)
    assert (state, message) == (FAILED, "out of memory")
    assert worker.outputs == []
    assert work_dirs() == []


def test_audio_separator_unavailable(pipeline, monkeypatch, tmp_path):
    monkeypatch.setattr(worker_module, "HAS_AUDIO_SEPARATOR", False)
    _, (state, message), _ = run_worker(VIDEO_URL, tmp_path, "audio_separator", "roformer")
    assert state == FAILED
    assert "audio_separator could not be loaded" in message


def test_cancel_during_extraction(pipeline, tmp_path):
    holder = {}

    def cancel_midway(status_cb, progress_cb):
        holder["worker"].cancel()
        progress_cb(50)  # the next callback notices the cancellation
        raise AssertionError("not reached")
    pipeline["on_extract"] = cancel_midway

    original_init = Worker.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        holder["worker"] = self
    Worker.__init__ = init
    try:
        _, (state, _message), _ = run_worker(VIDEO_URL, tmp_path)
    finally:
        Worker.__init__ = original_init
    assert state == CANCELLED
    assert work_dirs() == []


def test_playlist_goes_on_after_a_failure(pipeline, monkeypatch, tmp_path):
    urls = [f"https://www.youtube.com/watch?v=video{i}0000" for i in range(3)]
    monkeypatch.setattr(FakePlaylist, "urls", urls)
    pipeline["fail"] = {urls[1]}
    worker, (state, message), statuses = run_worker(PLAYLIST_URL, tmp_path)
    assert state == DONE
    assert message == "1 of 3 videos failed"
    assert len(worker.outputs) == 2
    assert "Video 3/3: " + urls[2] in statuses


def test_playlist_all_failed(pipeline, monkeypatch, tmp_path):
    urls = [f"https://www.youtube.com/watch?v=video{i}0000" for i in range(2)]
    monkeypatch.setattr(FakePlaylist, "urls", urls)
    pipeline["fail"] = set(urls)
    _, (state, message), _ = run_worker(PLAYLIST_URL, tmp_path)
    assert (state, message) == (FAILED, "All 2 videos failed")


def test_gpu_env_extraction_killed_by_cancel(pipeline, monkeypatch, tmp_path):
    """cancel() kills the GPU environment's subprocess, and the job then
    reports being stopped, not the subprocess' exit code."""
    monkeypatch.setattr(worker_module.gpu_env, "status", lambda env_dir: "ready")

    class FakeProc:
        terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    proc = FakeProc()
    holder = {}

    def run_extraction(env_dir, flac_path, out_dir, backend, model, status_cb,
                       progress_cb, model_dir=None, on_start=None):
        on_start(proc)
        holder["worker"].cancel()
        assert proc.terminated
        raise RuntimeError("GPU extraction subprocess exited with code -15")
    monkeypatch.setattr(worker_module.gpu_env, "run_extraction", run_extraction)

    worker = Worker(VIDEO_URL, str(tmp_path), "openunmix", None)
    holder["worker"] = worker
    results = []
    worker.job_finished.connect(lambda state, message: results.append(state))
    worker.run()
    assert results == [CANCELLED]


def test_stems_resampled_to_the_jobs_rate(pipeline, monkeypatch, tmp_path):
    resampled = []
    monkeypatch.setattr(worker_module, "resample_wav",
                        lambda path, rate: resampled.append((path, rate)) or True)
    worker = Worker(VIDEO_URL, str(tmp_path), "openunmix", None, sample_rate=48000)
    results = []
    worker.job_finished.connect(lambda state, message: results.append(state))
    worker.run()
    assert results == [DONE]
    assert resampled == [(worker.outputs[0], 48000)]
