import multiprocessing

# In the frozen app, the separation's child processes (see
# yaas/local_extraction.py) are this same executable: freeze_support() runs
# them and exits, before the GUI's heavy imports.
multiprocessing.freeze_support()

import yaas.app  # noqa: E402

if __name__ == "__main__":
    yaas.app.main()
