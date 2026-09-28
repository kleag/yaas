"""Child process targets for test_local_extraction.py: importable by
multiprocessing's spawned children, unlike functions local to a test."""
import os
import time


def report_and_finish(conn, out_dir):
    conn.send(("status", "working"))
    conn.send(("progress", 50))
    path = os.path.join(out_dir, "stem.wav")
    open(path, "w").close()
    conn.send(("done", [path]))
    conn.close()


def fail(conn):
    conn.send(("error", "model not found"))
    conn.close()


def crash(conn):
    os._exit(3)


def run_forever(conn, pid_file):
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    conn.send(("status", "started"))
    while True:
        conn.send(("progress", 1))
        time.sleep(0.2)


def compute_silently(conn):
    """Like OpenUnmix's separation: long, and reporting nothing."""
    conn.send(("status", "started"))
    time.sleep(60)
    conn.send(("done", []))
