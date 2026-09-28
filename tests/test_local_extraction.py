"""The separation's child process (local_extraction), with stand-in
targets from child_targets.py in real spawned processes."""
import threading
import time

import pytest

import child_targets
from yaas import local_extraction


def run(target, *args, status_cb=None, progress_cb=None, on_start=None):
    statuses, progress = [], []
    outputs = local_extraction._run_child(
        target, args, status_cb or statuses.append, progress_cb or progress.append,
        on_start)
    return outputs, statuses, progress


def test_reports_and_returns_outputs(tmp_path):
    outputs, statuses, progress = run(child_targets.report_and_finish, str(tmp_path))
    assert outputs == [str(tmp_path / "stem.wav")]
    assert (statuses, progress) == (["working"], [50])


def test_error_is_raised():
    with pytest.raises(RuntimeError, match="model not found"):
        run(child_targets.fail)


def test_crash_is_reported():
    with pytest.raises(RuntimeError, match="exited with code 3"):
        run(child_targets.crash)


def test_kill_interrupts_a_step_that_reports_nothing():
    """What Stop does to an OpenUnmix separation: Worker.cancel() kills the
    process handed to on_start, from the UI thread."""
    procs = []

    def kill_soon(proc):
        procs.append(proc)
        threading.Timer(1, proc.kill).start()

    start = time.monotonic()
    with pytest.raises(RuntimeError, match="exited with code"):
        run(child_targets.compute_silently, on_start=kill_soon)
    assert time.monotonic() - start < 30
    assert not procs[0].is_alive()


def test_raising_callback_kills_the_child(tmp_path):
    """Worker's callbacks raise Cancelled once stopped: the child must not
    go on running unattended."""
    procs = []

    class Stop(Exception):
        pass

    def progress_cb(value):
        raise Stop()

    with pytest.raises(Stop):
        run(child_targets.run_forever, str(tmp_path / "pid"),
            progress_cb=progress_cb, on_start=procs.append)
    assert not procs[0].is_alive()


def test_check_child_process():
    assert local_extraction.check_child_process()
