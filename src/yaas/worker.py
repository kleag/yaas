import functools
import os
import shutil
import tempfile
import threading
import time
import traceback

from PySide6.QtCore import QThread, Signal, QStandardPaths
from pytubefix import YouTube, Playlist
from yturl2mp3.config import Config
from yturl2mp3.helpers import (convert_to_flac, download_audio,
                               is_valid_playlist_url, is_valid_video_url)
from . import gpu_env, local_extraction
from .separate_worker import (HAS_AUDIO_SEPARATOR, audio_separator_unavailable_message,
                              resample_wav)

# Job outcomes, as sent by Worker.job_finished.
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

WORK_DIRNAME = "work"


def app_data_path():
    return QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)


def work_root():
    """Where jobs keep their intermediate files, one temporary folder each.
    Nothing in it outlives a job, except after a crash: see
    clean_work_root()."""
    return os.path.join(app_data_path(), WORK_DIRNAME)


def clean_work_root(max_age_s=24 * 3600):
    """Removes the intermediate files a crashed or killed run left behind.
    Only job folders untouched for max_age_s, as another Yaas instance may
    be running a job right now."""
    root = work_root()
    if not os.path.isdir(root):
        return
    for entry in os.scandir(root):
        try:
            if time.time() - entry.stat().st_mtime > max_age_s:
                shutil.rmtree(entry.path, ignore_errors=True)
        except OSError:
            pass


class Cancelled(Exception):
    """Raised inside the pipeline, from its progress callbacks, once the
    user clicked Stop."""


class Worker(QThread):
    """Runs one job (a video, or all the videos of a playlist) through the
    download -> FLAC -> separation pipeline, off the UI thread.

    The separation runs in a child process (local_extraction, or the GPU
    environment's), which cancel() kills, whatever it is doing. Before
    that, cancel() sets a flag checked between steps and in the download's
    progress callback. Only the FLAC conversion, a few seconds long, isn't
    interrupted."""
    update_status = Signal(str)
    # 0-100, or -1 while a step gives no progress estimate.
    progress = Signal(int)
    # (DONE/FAILED/CANCELLED, message), emitted exactly once, at the end.
    job_finished = Signal(str, str)

    def __init__(self, url, out_dir, backend, model, sample_rate=None, parent=None):
        super().__init__(parent)
        self.url = url
        self.out = out_dir
        self.backend_type = backend or "audio_separator"
        self.model_type = model
        # The stems' sample rate, or None to keep the model's.
        self.sample_rate = sample_rate
        self.gpu_env_dir = os.path.join(app_data_path(), gpu_env.GPU_ENV_DIRNAME)
        # audio_separator's own default model cache dir is /tmp/..., which
        # isn't persistent on most Linux systems (/tmp is commonly wiped on
        # reboot). Use Qt's cross-platform cache location instead, so
        # downloaded models are kept for future runs.
        self.models_dir = os.path.join(
            QStandardPaths.writableLocation(QStandardPaths.CacheLocation),
            "audio-separator-models")
        self.outputs = []
        self._cancel = threading.Event()
        self._proc = None
        self._proc_lock = threading.Lock()

    def cancel(self):
        """Asks the job to stop. Safe to call from any thread."""
        self._cancel.set()
        with self._proc_lock:
            if self._proc is not None:
                _kill(self._proc)

    def is_cancelled(self):
        return self._cancel.is_set()

    def run(self):
        work_dir = None
        try:
            os.makedirs(self.out, exist_ok=True)
            os.makedirs(work_root(), exist_ok=True)
            work_dir = tempfile.mkdtemp(prefix="job-", dir=work_root())
            state, message = self._run_pipeline(work_dir)
        except Cancelled:
            state, message = CANCELLED, "Stopped"
        except Exception as ex:
            traceback.print_exc()
            state, message = FAILED, _describe(ex)
        finally:
            if work_dir:
                shutil.rmtree(work_dir, ignore_errors=True)
        self.job_finished.emit(state, message)

    def _run_pipeline(self, work_dir):
        urls = self._video_urls()
        failures = []
        for i, url in enumerate(urls, 1):
            if len(urls) > 1:
                self._status(f"Video {i}/{len(urls)}: {url}")
            try:
                self.outputs += self._process_video(url, work_dir)
            except Cancelled:
                raise
            except Exception as ex:
                traceback.print_exc()
                failures.append(_describe(ex))
                self._status(f"Failed: {url}: {failures[-1]}")
        if len(urls) == 1 and failures:
            return FAILED, failures[0]
        if failures and not self.outputs:
            return FAILED, f"All {len(urls)} videos failed"
        if failures:
            return DONE, f"{len(failures)} of {len(urls)} videos failed"
        return DONE, ""

    def _video_urls(self):
        if is_valid_video_url(self.url):
            return [self.url]
        if is_valid_playlist_url(self.url):
            self._status("Listing the playlist's videos...")
            self.progress.emit(-1)
            urls = list(Playlist(self.url).video_urls)
            self._check_cancelled()
            if not urls:
                raise RuntimeError("The playlist is empty")
            return urls
        raise ValueError(f"Not a YouTube video or playlist URL: {self.url}")

    def _process_video(self, url, work_dir):
        self._status(f"Downloading audio from {url}...")
        self.progress.emit(-1)
        video = YouTube(url, "WEB", on_progress_callback=self._download_progress)
        config = Config(out_dir=work_dir, timeout=5000, max_retries=3)
        downloaded = download_audio(video, config)
        try:
            flac_path = os.path.splitext(downloaded)[0] + ".flac"
            self._status("Converting to FLAC...")
            self.progress.emit(-1)
            convert_to_flac(downloaded, flac_path)
        finally:
            os.remove(downloaded)
        try:
            return self._extract_tracks(flac_path)
        finally:
            os.remove(flac_path)

    def _download_progress(self, stream, chunk, bytes_remaining):
        if stream.filesize:
            self._progress(int((stream.filesize - bytes_remaining) * 100 / stream.filesize))
        else:
            self._check_cancelled()

    def _extract_tracks(self, flac_path):
        self._status(f"Extracting tracks with {self.backend_type}"
                     + (f" ({self.model_type})" if self.backend_type == "audio_separator" else "")
                     + "...")
        self.progress.emit(-1)
        if gpu_env.status(self.gpu_env_dir) == "ready":
            self._status("Using the GPU-accelerated environment...")
            run_extraction = functools.partial(gpu_env.run_extraction, self.gpu_env_dir)
        else:
            if self.backend_type == "audio_separator" and not HAS_AUDIO_SEPARATOR:
                raise RuntimeError(audio_separator_unavailable_message())
            run_extraction = local_extraction.run_extraction
        try:
            outputs = run_extraction(
                flac_path, self.out, self.backend_type, self.model_type,
                self._status, self._progress, model_dir=self.models_dir,
                on_start=self._set_proc)
        except RuntimeError:
            # Killed by cancel(): report that, not the exit code.
            self._check_cancelled()
            raise
        finally:
            self._set_proc(None)
        self._check_cancelled()
        if self.sample_rate:
            self._resample(outputs)
        return outputs

    def _resample(self, outputs):
        """In this process: a few seconds per video, done file by file, so
        Stop is only delayed by one file's resampling."""
        for i, path in enumerate(outputs):
            self._progress(int(i * 100 / len(outputs)))
            if resample_wav(path, self.sample_rate):
                self._status(f"Resampled {os.path.basename(path)} to {self.sample_rate} Hz")

    def _set_proc(self, proc):
        with self._proc_lock:
            self._proc = proc
            if proc is not None and self.is_cancelled():
                _kill(proc)

    def _check_cancelled(self):
        if self.is_cancelled():
            raise Cancelled()

    # The callbacks handed to the download and separation code: raising
    # Cancelled from them is what interrupts a long step.
    def _status(self, message):
        self._check_cancelled()
        self.update_status.emit(message)

    def _progress(self, value):
        self._check_cancelled()
        self.progress.emit(value)


def _kill(proc):
    """Kills a subprocess.Popen or multiprocessing.Process, which may have
    ended already."""
    try:
        proc.kill()
    except (OSError, ValueError):
        pass


def _describe(ex):
    return str(ex) or ex.__class__.__name__
