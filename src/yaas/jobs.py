"""The job queue: jobs are added while another one runs, and run one at a
time, in order, each on its own `Worker` thread.

Kept free of widgets so the queueing logic can be tested without a window;
`MainWindow` only renders the jobs and forwards the user's actions.
"""
import re

from PySide6.QtCore import QObject, Signal, Slot

from .worker import CANCELLED, DONE, FAILED, Worker

QUEUED = "queued"
RUNNING = "running"


def page_title_to_job_title(title):
    """"(3) Artist - Song - YouTube" -> "Artist - Song"."""
    title = re.sub(r"^\(\d+\)\s*", "", title or "")
    return re.sub(r"\s*-\s*YouTube( Music)?$", "", title).strip()


class Job:
    """One URL to split, with the output folder, model and stems sample rate
    it was queued with: changing the settings afterwards only affects jobs
    queued later."""

    def __init__(self, url, title, out_dir, backend, model, sample_rate=None):
        self.url = url
        self.title = title or url
        self.out_dir = out_dir
        self.backend = backend
        self.model = model
        self.sample_rate = sample_rate
        self.state = QUEUED
        self.message = ""
        self.outputs = []

    @property
    def finished(self):
        return self.state in (DONE, FAILED, CANCELLED)


class JobQueue(QObject):
    job_added = Signal(object)
    job_changed = Signal(object)
    job_removed = Signal(object)
    # Status messages and progress of the running job.
    status = Signal(str)
    progress = Signal(int)
    # Whether a job is running.
    busy_changed = Signal(bool)

    def __init__(self, worker_factory=Worker, parent=None):
        super().__init__(parent)
        self._worker_factory = worker_factory
        self.jobs = []
        self.current = None
        self._worker = None

    @property
    def busy(self):
        return self._worker is not None

    def add(self, job):
        self.jobs.append(job)
        self.job_added.emit(job)
        self._start_next()

    def remove(self, job):
        """Removes a job that isn't running."""
        if job is self.current or job not in self.jobs:
            return
        self.jobs.remove(job)
        self.job_removed.emit(job)

    def clear_finished(self):
        for job in [j for j in self.jobs if j.finished]:
            self.remove(job)

    def stop_current(self):
        """Stops the running job; the next queued one then starts."""
        if self._worker is not None:
            self._worker.cancel()

    def shutdown(self, timeout_ms):
        """Drops the queued jobs and stops the running one, waiting up to
        timeout_ms for it. Returns whether no job is running anymore."""
        for job in [j for j in self.jobs if j.state == QUEUED]:
            self.remove(job)
        if self._worker is None:
            return True
        self._worker.cancel()
        return self._worker.wait(timeout_ms)

    def _start_next(self):
        if self._worker is not None:
            return
        job = next((j for j in self.jobs if j.state == QUEUED), None)
        if job is None:
            return
        self.current = job
        job.state = RUNNING
        self.job_changed.emit(job)
        worker = self._worker_factory(job.url, job.out_dir, job.backend, job.model,
                                      sample_rate=job.sample_rate)
        # Signal to signal and to this object's slots: queued connections,
        # delivered on the UI thread.
        worker.update_status.connect(self.status)
        worker.progress.connect(self.progress)
        worker.job_finished.connect(self._job_finished)
        worker.finished.connect(self._worker_finished)
        self._worker = worker
        self.busy_changed.emit(True)
        worker.start()

    @Slot(str, str)
    def _job_finished(self, state, message):
        job = self.current
        job.state = state
        job.message = message
        job.outputs = list(self._worker.outputs)

    @Slot()
    def _worker_finished(self):
        # QThread.finished rather than job_finished: the thread must really
        # be over before its Worker is dropped.
        job = self.current
        if job.state == RUNNING:  # run() died without reporting
            job.state = FAILED
            job.message = job.message or "The job ended unexpectedly"
        self._worker.deleteLater()
        self._worker = None
        self.current = None
        self.job_changed.emit(job)
        self.busy_changed.emit(False)
        self._start_next()
