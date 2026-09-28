import os
import sys
import tempfile
import time

import pytest

# Keep the tests' QStandardPaths locations (app data, settings, caches) out
# of the real user's: point them at a throwaway home before Qt reads them.
_HOME = tempfile.mkdtemp(prefix="yaas-tests-home-")
os.environ["HOME"] = _HOME
for var in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[var] = os.path.join(_HOME, var.lower())
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "src"))

from PySide6.QtCore import QCoreApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    app.setApplicationName("yaas-tests")
    return app


def wait_until(condition, timeout=10):
    """Runs the Qt event loop until condition() holds."""
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("Timed out waiting for condition")
        QCoreApplication.processEvents()
        time.sleep(0.01)
