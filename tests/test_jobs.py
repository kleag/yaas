import threading

import pytest
from PySide6.QtCore import QThread, Signal

from conftest import wait_until
from yaas.jobs import QUEUED, RUNNING, Job, JobQueue, page_title_to_job_title
from yaas.worker import CANCELLED, DONE, FAILED


class FakeWorker(QThread):
    """Runs until released (or cancelled), then reports `outcome`."""
    update_status = Signal(str)
    progress = Signal(int)
    job_finished = Signal(str, str)
    started_urls = []
    outcomes = {}

    def __init__(self, url, out_dir, backend, model, sample_rate=None):
        super().__init__()
        self.url = url
        self.outputs = []
        self.release = threading.Event()
        self.cancelled = False
        FakeWorker.instances[url] = self

    def cancel(self):
        self.cancelled = True
        self.release.set()

    def run(self):
        FakeWorker.started_urls.append(self.url)
        self.release.wait(10)
        if self.cancelled:
            self.job_finished.emit(CANCELLED, "Stopped")
            return
        state = FakeWorker.outcomes.get(self.url, DONE)
        if state == DONE:
            self.outputs = [f"/out/{self.url}.wav"]
        self.job_finished.emit(state, "" if state == DONE else "boom")


@pytest.fixture
def queue(qapp):
    FakeWorker.instances = {}
    FakeWorker.started_urls = []
    FakeWorker.outcomes = {}
    queue = JobQueue(worker_factory=FakeWorker)
    yield queue
    queue.shutdown(5000)
    wait_until(lambda: not queue.busy)


def make_job(url):
    return Job(url, "", "/out", "openunmix", None)


def finish(url):
    wait_until(lambda: url in FakeWorker.instances)
    FakeWorker.instances[url].release.set()


def test_jobs_run_one_at_a_time_in_order(queue):
    a, b, c = make_job("a"), make_job("b"), make_job("c")
    for job in (a, b, c):
        queue.add(job)
    assert queue.busy
    assert (a.state, b.state, c.state) == (RUNNING, QUEUED, QUEUED)

    finish("a")
    wait_until(lambda: b.state == RUNNING)
    assert a.state == DONE and a.outputs == ["/out/a.wav"]
    assert c.state == QUEUED

    finish("b")
    finish("c")
    wait_until(lambda: c.finished and not queue.busy)
    assert FakeWorker.started_urls == ["a", "b", "c"]


def test_failure_is_reported_and_queue_goes_on(queue):
    FakeWorker.outcomes["a"] = FAILED
    a, b = make_job("a"), make_job("b")
    queue.add(a)
    queue.add(b)
    finish("a")
    wait_until(lambda: b.state == RUNNING)
    assert (a.state, a.message) == (FAILED, "boom")


def test_stop_current_then_next_starts(queue):
    a, b = make_job("a"), make_job("b")
    queue.add(a)
    queue.add(b)
    wait_until(lambda: "a" in FakeWorker.started_urls)
    queue.stop_current()
    wait_until(lambda: b.state == RUNNING)
    assert a.state == CANCELLED


def test_remove_queued_job(queue):
    a, b, c = make_job("a"), make_job("b"), make_job("c")
    removed = []
    queue.job_removed.connect(removed.append)
    for job in (a, b, c):
        queue.add(job)
    queue.remove(a)  # running: not removable
    queue.remove(b)
    assert removed == [b]
    assert queue.jobs == [a, c]
    finish("a")
    finish("c")
    wait_until(lambda: c.finished)
    assert "b" not in FakeWorker.started_urls


def test_clear_finished(queue):
    a, b = make_job("a"), make_job("b")
    queue.add(a)
    queue.add(b)
    finish("a")
    wait_until(lambda: a.finished)
    queue.clear_finished()
    assert queue.jobs == [b]


def test_shutdown_drops_queue_and_stops_running_job(queue):
    a, b = make_job("a"), make_job("b")
    queue.add(a)
    queue.add(b)
    wait_until(lambda: "a" in FakeWorker.started_urls)
    assert queue.shutdown(5000)
    assert queue.jobs == [a]
    wait_until(lambda: not queue.busy)
    assert a.state == CANCELLED
    assert FakeWorker.started_urls == ["a"]


@pytest.mark.parametrize("page_title, job_title", [
    ("Artist - Song - YouTube", "Artist - Song"),
    ("(3) Artist - Song - YouTube", "Artist - Song"),
    ("Song - YouTube Music", "Song"),
    ("", ""),
])
def test_page_title_to_job_title(page_title, job_title):
    assert page_title_to_job_title(page_title) == job_title


def test_job_title_falls_back_to_url():
    assert Job("https://youtu.be/x", "", "/out", "openunmix", None).title == "https://youtu.be/x"
