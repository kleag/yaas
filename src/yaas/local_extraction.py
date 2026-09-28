"""Runs the separation in a child process, so that Stop can end it at any
point: neither OpenUnmix nor a model's loading report any progress to be
interrupted at, and a Python thread can't be killed safely.

multiprocessing's "spawn" mode rather than a subprocess speaking over stdout
(as gpu_env does): a windowed Windows build has no usable stdout, and spawn
works the same in a frozen app (see multiprocessing.freeze_support() in
pyinstmain.py and app.main()) as from source. Never "fork": the parent is a
multi-threaded Qt process.

The child only imports yaas.separate_worker. It inherits the environment
app.py prepared (PATH with the bundled ffmpeg, SSL_CERT_FILE).
"""
import multiprocessing

from . import separate_worker

_EXIT_WAIT_S = 30


def run_extraction(flac_path, out_dir, backend, model, status_cb, progress_cb,
                   model_dir=None, on_start=None):
    """Same interface as gpu_env.run_extraction: on_start, if given,
    receives the child process, which the caller can kill() to cancel.
    Returns the written stems' paths."""
    return _run_child(separate_worker.child_main,
                      (flac_path, out_dir, backend, model, model_dir),
                      status_cb, progress_cb, on_start)


def check_child_process():
    """Starts a trivial child process; returns the interpreter it ran."""
    return _run_child(separate_worker.child_ping, (), print, print, None)[0]


def _run_child(target, args, status_cb, progress_cb, on_start):
    ctx = multiprocessing.get_context("spawn")
    reader, writer = ctx.Pipe(duplex=False)
    # daemon: killed if the app exits normally while it runs.
    proc = ctx.Process(target=target, args=(writer, *args), daemon=True)
    proc.start()
    # Only the child holds the write end now, so its death ends recv() below.
    writer.close()
    if on_start is not None:
        on_start(proc)
    outputs = None
    try:
        while True:
            try:
                kind, payload = reader.recv()
            except EOFError:
                break
            if kind == "status":
                status_cb(payload)
            elif kind == "progress":
                progress_cb(payload)
            elif kind == "error":
                raise RuntimeError(payload)
            elif kind == "done":
                outputs = payload
    finally:
        # Also reached when a callback raises (Worker's do once cancelled):
        # the child mustn't go on without anyone listening.
        reader.close()
        proc.join(_EXIT_WAIT_S if outputs is not None else 0)
        if proc.is_alive():
            proc.kill()
            proc.join()
    if outputs is None:
        raise RuntimeError(f"The separation process exited with code {proc.exitcode}")
    return outputs
