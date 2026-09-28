import argparse
import html
import multiprocessing
import os
import subprocess
import sys


def _setup_ffmpeg_path():
    """Make ffmpeg/ffprobe findable by plain name, as pydub, audio_separator
    and check_ffmpeg() all look them up on PATH. This must run before pydub
    is imported (via .worker below), since pydub looks ffmpeg up once at
    import time.

    The macOS dmg ships static builds in bundled_ffmpeg/ (see yaas.spec);
    those come first. Beyond that, macOS apps launched from Finder/the Dock
    don't inherit the user's shell PATH: they get only
    /usr/bin:/bin:/usr/sbin:/sbin, so an ffmpeg installed with Homebrew or
    MacPorts would never be found even though it works in a terminal. Add
    their standard bin directories too, as a fallback."""
    path = os.environ.get("PATH", "").split(os.pathsep)
    extra = []
    if getattr(sys, "frozen", False):
        extra.append(os.path.join(sys._MEIPASS, "bundled_ffmpeg"))
    if sys.platform == "darwin":
        extra += ["/opt/homebrew/bin",  # Homebrew, Apple Silicon
                  "/usr/local/bin",     # Homebrew, Intel
                  "/opt/local/bin"]     # MacPorts
    extra = [d for d in extra if os.path.isdir(d) and d not in path]
    os.environ["PATH"] = os.pathsep.join(extra + path)


_setup_ffmpeg_path()


def _setup_ssl_certificates():
    """Give Python's ssl module a CA bundle when the system one is missing.

    A frozen app's OpenSSL looks for CA certificates at the path compiled
    into the *build machine's* Python. With python.org's macOS build that's
    a cert.pem inside its own framework, which doesn't exist on users'
    Macs, so every HTTPS request from Python (pytubefix's downloads
    included) fails with "certificate verify failed". The embedded browser
    is unaffected, as Qt WebEngine has its own certificate handling. Only
    fall back to certifi's bundle when neither default location exists, so
    a working system store (with any locally added CAs) is kept, and never
    override an SSL_CERT_FILE the user set themselves.

    Must run before anything in the process makes a TLS connection:
    OpenSSL reads SSL_CERT_FILE once, on first use, and ignores later
    changes (confirmed: setting it after a failed request doesn't help)."""
    import ssl
    if os.environ.get("SSL_CERT_FILE"):
        return
    paths = ssl.get_default_verify_paths()
    # An existing but empty capath is common too (python.org's Python
    # installed without running its "Install Certificates" script).
    if paths.cafile or (paths.capath and os.path.isdir(paths.capath)
                        and os.listdir(paths.capath)):
        return
    try:
        import certifi
    except ImportError:
        return
    os.environ["SSL_CERT_FILE"] = certifi.where()


_setup_ssl_certificates()

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTextBrowser, QMessageBox, QSizePolicy,
                               QProgressBar, QToolButton, QMenu, QDialog,
                               QFormLayout, QDialogButtonBox, QFileDialog,
                               QComboBox, QListWidget, QListWidgetItem,
                               QSplitter, QStyle)
from PySide6.QtCore import (Qt, QSize, QStandardPaths, QThread, QUrl, Signal, Slot)
from PySide6.QtGui import (QDesktopServices, QIcon, QPixmap, QTextCharFormat,
                           QTextCursor)

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

from yturl2mp3.helpers import is_valid_playlist_url, is_valid_video_url
from . import __version__
from . import gpu_env
from . import settings
from .jobs import Job, JobQueue, QUEUED, RUNNING, page_title_to_job_title
from .worker import CANCELLED, DONE, FAILED, clean_work_root

DOCUMENTATION_URL = "https://kleag.github.io/yaas/"
ISSUES_URL = "https://github.com/kleag/yaas/issues"
HOMEPAGE_URL = "https://github.com/kleag/yaas"


def icon_path():
    """Locate the app icon, bundled into the frozen app on Windows/Linux the
    same way as separate_worker.py (see gpu_env.py), or shipped as package
    data next to this module for a source/pip-installed run. Windows uses
    the .ico (multi-resolution, crisper for title bar/taskbar); everywhere
    else uses the plain PNG."""
    name = "icon.ico" if sys.platform == "win32" else "icon.png"
    if getattr(sys, "frozen", False):
        candidate = os.path.join(sys._MEIPASS, "yaas", "resources", name)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(os.path.dirname(__file__), "resources", name)


try:
    from ctypes import windll  # Only exists on Windows.
    myappid = 'kleag.yaas.0'
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass


class GpuInstallThread(QThread):
    status_update = Signal(str)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, env_dir):
        super().__init__()
        self.env_dir = env_dir

    def run(self):
        try:
            gpu_env.install(self.env_dir, self.status_update.emit)
        except BaseException as ex:
            self.failed.emit(str(ex))
            return
        self.finished_ok.emit()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)

        self.output_dir = settings.get_output_dir()

        form = QFormLayout()

        self.output_dir_row = QHBoxLayout()
        self.output_dir_input = QLineEdit(self.output_dir)
        self.output_dir_input.setReadOnly(True)
        self.output_dir_row.addWidget(self.output_dir_input)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_output_dir)
        self.output_dir_row.addWidget(self.browse_button)
        form.addRow("Output folder:", self.output_dir_row)

        self.model_combo = QComboBox()
        for key, (label, _backend, _model) in settings.MODELS.items():
            self.model_combo.addItem(label, key)
        self.model_combo.setCurrentIndex(
            self.model_combo.findData(settings.get_model()))
        form.addRow("Separation model:", self.model_combo)

        self.sample_rate_combo = QComboBox()
        for rate, label in settings.SAMPLE_RATES.items():
            self.sample_rate_combo.addItem(label, rate)
        self.sample_rate_combo.setCurrentIndex(
            self.sample_rate_combo.findData(settings.get_sample_rate()))
        form.addRow("Stems sample rate:", self.sample_rate_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def browse_output_dir(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.output_dir)
        if chosen:
            self.output_dir = chosen
            self.output_dir_input.setText(chosen)

    def save(self):
        settings.set_output_dir(self.output_dir)
        settings.set_model(self.model_combo.currentData())
        settings.set_sample_rate(self.sample_rate_combo.currentData())
        self.accept()


STOP_BUTTON_STYLE = """
QPushButton {
    background-color: #c62828; color: white; font-weight: bold;
    border: none; border-radius: 4px; padding: 6px 16px;
}
QPushButton:hover { background-color: #b71c1c; }
QPushButton:disabled { background-color: #e57373; }
"""

JOB_STATE_LABELS = {
    QUEUED: "Queued",
    RUNNING: "Running",
    DONE: "Done",
    FAILED: "Failed",
    CANCELLED: "Stopped",
}


def parse_args() -> argparse.Namespace:
    """
    Parse the command line arguments. Unknown ones are left for Qt.

    :return: The parsed argument namespace
    """
    parser = argparse.ArgumentParser(
        prog="yaas",
        description="Yaas (Yet Another Audio Splitter): splits the soundtrack "
                    "of YouTube videos into separate stems.")

    parser.add_argument(
        '--version', action='version', version=f"%(prog)s {__version__}")

    parser.add_argument(
        '-o', '--out', metavar="DIR", type=str,
        default=None,
        help="The directory in which to write the stems. "
             "Overrides the Settings dialog's output folder for this run "
             "only; defaults to it if not given.")

    parser.add_argument(
        '--backend', metavar="BACKEND", type=str,
        default=None,
        choices=["audio_separator", "openunmix"],
        help="The backend to use for track separation (openunmix, "
             "audio_separator). Overrides the Settings dialog's model "
             "for this run only; defaults to it if not given.")

    parser.add_argument(
        '--model', metavar="MODEL", type=str,
        default=None,
        choices=["roformer", "htdemucs6s"],
        help="The model to use with audio_separator backend (roformer, "
             "htdemucs6s). Overrides the Settings dialog's model for "
             "this run only; defaults to it if not given.")

    parser.add_argument(
        '--sample-rate', metavar="HZ", type=int,
        default=None,
        choices=list(settings.SAMPLE_RATES),
        help="The stems' sample rate (%(choices)s). Overrides the Settings "
             "dialog's sample rate for this run only; defaults to it if "
             "not given.")

    return parser.parse_known_args()[0]


class MainWindow(QWidget):
    def __init__(self, args):
        super().__init__()
        initial_url = "https://www.youtube.com"
        self.args = args
        if not self.args.out:
            self.args.out = settings.get_output_dir()
        if not self.args.sample_rate:
            self.args.sample_rate = settings.get_sample_rate()
        # --backend/--model override the Settings dialog's model for this
        # run only, like --out does for the output folder.
        if self.args.backend is None and self.args.model is None:
            self.apply_model_setting()
        else:
            self.args.backend = self.args.backend or "audio_separator"
            if self.args.backend == "openunmix":
                self.args.model = None
            else:
                self.args.model = self.args.model or "roformer"

        # No job runs yet: remove what a crashed run left behind.
        clean_work_root()

        self.setWindowTitle("Yaas - Yet Another Audio Splitter")
        self.setWindowIcon(QIcon(icon_path()))
        self.setGeometry(100, 100, 1024, 768)

        self.layout = QVBoxLayout()

        self.menu_button = QToolButton()
        self.menu_button.setText("☰")  # Hamburger icon (☰)
        self.menu_button.setToolTip("Menu")
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        self.menu_button.setAutoRaise(True)
        self.menu_button.setFixedSize(32, 32)
        font = self.menu_button.font()
        font.setPointSize(font.pointSize() + 4)
        self.menu_button.setFont(font)

        self.gpu_env_dir = os.path.join(
            QStandardPaths.writableLocation(QStandardPaths.AppDataLocation),
            gpu_env.GPU_ENV_DIRNAME)
        self.gpu_install_thread = None

        self.main_menu = QMenu(self.menu_button)
        self.main_menu.addAction("Settings...", self.open_settings_dialog)
        self.main_menu.addAction("Open Output Folder", self.open_output_folder)
        self.main_menu.addSeparator()
        self.main_menu.addAction("Documentation", self.open_documentation)
        self.main_menu.addAction("Report an Issue", self.open_issues)
        if gpu_env.is_supported_platform():
            self.main_menu.addAction("GPU Acceleration...", self.open_gpu_dialog)
        elif gpu_env.is_apple_silicon():
            self.main_menu.addAction("GPU Acceleration...", self.open_mps_dialog)
        self.main_menu.addSeparator()
        self.main_menu.addAction("About Yaas", self.show_about)
        self.menu_button.setMenu(self.main_menu)

        self.label = QLabel("Enter YouTube URL:")

        self.url_input = QLineEdit(initial_url)
        self.url_input.editingFinished.connect(self.url_changed)

        self.url_bar = QHBoxLayout()
        self.url_bar.addWidget(self.label)
        self.url_bar.addWidget(self.url_input)
        self.url_bar.addWidget(self.menu_button)
        self.layout.addLayout(self.url_bar)

        self.browser = QWebEngineView()
        # Set up a persistent profile
        self.setup_persistent_profile()

        self.browser.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.browser.setUrl(initial_url)
        self.browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.browser.urlChanged.connect(self.update_line_edit)

        self.start_button = QPushButton("Start")
        self.start_button.setToolTip(
            "Split the soundtrack of the video or playlist shown above. "
            "While a job runs, this queues another one.")
        self.start_button.clicked.connect(self.start_process)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setToolTip("Stop the running job. Queued jobs then go on.")
        self.stop_button.setStyleSheet(STOP_BUTTON_STYLE)
        self.stop_button.clicked.connect(self.stop_process)
        self.stop_button.hide()

        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(self.stop_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()

        self.job_list = QListWidget()
        self.job_list.setIconSize(QSize(16, 16))
        self.job_list.setToolTip("Jobs. Right-click for actions; double-click "
                                 "a finished job to open its output folder.")
        self.job_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.job_list.customContextMenuRequested.connect(self.show_job_menu)
        self.job_list.itemDoubleClicked.connect(self.job_double_clicked)
        self.job_items = {}

        # A QTextBrowser, for its clickable links to the written stems.
        self.status_output = QTextBrowser()
        self.status_output.setOpenLinks(False)
        self.status_output.anchorClicked.connect(QDesktopServices.openUrl)

        log_panel = QSplitter(Qt.Horizontal)
        log_panel.addWidget(self.job_list)
        log_panel.addWidget(self.status_output)
        log_panel.setStretchFactor(0, 1)
        log_panel.setStretchFactor(1, 2)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addLayout(buttons)
        bottom_layout.addWidget(self.progress_bar)
        bottom_layout.addWidget(log_panel)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.browser)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([560, 200])
        self.layout.addWidget(splitter)

        self.setLayout(self.layout)

        self.queue = JobQueue(parent=self)
        self.queue.job_added.connect(self.job_added)
        self.queue.job_changed.connect(self.job_changed)
        self.queue.job_removed.connect(self.job_removed)
        self.queue.status.connect(self.update_status)
        self.queue.progress.connect(self.update_progress)
        self.queue.busy_changed.connect(self.busy_changed)

    def setup_persistent_profile(self):
        # Create a custom profile with a persistent storage path
        profile = QWebEngineProfile("yaas", self)

        # Optionally, set persistent cookies policy
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.ForcePersistentCookies)

        # Create a new page with the custom profile
        page = QWebEnginePage(profile, self.browser)

        # Set this page for the QWebEngineView
        self.browser.setPage(page)

    def update_line_edit(self, url):
        # Convert QUrl to string and set the text of QLineEdit
        self.url_input.setText(url.toString())

    def show_about(self):
        QMessageBox.about(
            self,
            "About Yaas",
            f"<h3>Yaas (Yet Another Audio Splitter)</h3>"
            f"<p>Version {__version__}</p>"
            f"<p>Splits YouTube video soundtracks into separate stems "
            f"(vocals, drums, bass, other, ...).</p>"
            f"<p>Gaël de Chalendar, aka Kleag<br>"
            f"(c) Gaël de Chalendar, 2024-2026</p>"
            f"<p>Licensed under the Mozilla Public License 2.0 (MPL 2.0).</p>"
            f"<p><a href=\"{HOMEPAGE_URL}\">{HOMEPAGE_URL}</a></p>")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.args.out = settings.get_output_dir()
            self.update_status(f"Output folder set to {self.args.out}")
            self.apply_model_setting()
            label = settings.MODELS[settings.get_model()][0]
            self.update_status(f"Separation model set to {label}")
            self.args.sample_rate = settings.get_sample_rate()
            self.update_status("Stems sample rate set to "
                               f"{settings.SAMPLE_RATES[self.args.sample_rate]}")
            if self.queue.busy:
                self.update_status("Already queued jobs keep their previous settings.")

    def apply_model_setting(self):
        _label, self.args.backend, self.args.model = settings.MODELS[
            settings.get_model()]

    def open_output_folder(self, path=None):
        path = path or self.args.out
        os.makedirs(path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_documentation(self):
        QDesktopServices.openUrl(QUrl(DOCUMENTATION_URL))

    def open_issues(self):
        QDesktopServices.openUrl(QUrl(ISSUES_URL))

    def open_gpu_dialog(self):
        current_status = gpu_env.status(self.gpu_env_dir)
        status_text = {
            "not_installed": "Not installed.",
            "stale": "Installed for a different Yaas version; reinstall recommended.",
            "ready": "Installed and ready.",
        }.get(current_status, current_status)

        box = QMessageBox(self)
        box.setWindowTitle("GPU Acceleration")
        box.setText(
            f"GPU acceleration status: {status_text}\n\n"
            "This provisions a separate, self-contained Python environment "
            "with CUDA-capable PyTorch, used automatically for extraction "
            "when ready. Requires an NVIDIA GPU with CUDA support.")
        install_label = "Reinstall" if current_status in ("ready", "stale") else "Install"
        install_button = box.addButton(install_label, QMessageBox.AcceptRole)
        remove_button = None
        if current_status in ("ready", "stale"):
            remove_button = box.addButton("Remove", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked is not install_button and (remove_button is None
                                              or clicked is not remove_button):
            return
        if self.queue.busy:
            QMessageBox.information(
                self, "GPU Acceleration",
                "Please wait for the running jobs to finish, or stop them, "
                "before changing the GPU acceleration environment.")
            return
        if clicked == install_button:
            self.confirm_and_install_gpu_env()
        else:
            gpu_env.uninstall(self.gpu_env_dir)
            self.update_status("GPU acceleration environment removed.")

    def open_mps_dialog(self):
        if gpu_env.mps_available():
            status_text = ("Available: extraction automatically uses this "
                           "Mac's GPU through Apple's Metal (MPS) backend.")
        else:
            status_text = ("Not available: Metal (MPS) couldn't be initialized "
                           "on this Mac, so extraction runs on CPU.")
        QMessageBox.information(
            self, "GPU Acceleration",
            f"GPU acceleration status: {status_text}\n\n"
            "On Apple Silicon Macs, GPU support is built into Yaas: there is "
            "nothing extra to install.")

    def confirm_and_install_gpu_env(self):
        confirm = QMessageBox.question(
            self, "Install GPU Acceleration",
            "This downloads several GB of GPU-accelerated libraries "
            "(CUDA-enabled PyTorch and related packages). Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return

        self.gpu_install_thread = GpuInstallThread(self.gpu_env_dir)
        self.gpu_install_thread.status_update.connect(self.update_status)
        self.gpu_install_thread.finished_ok.connect(self.gpu_install_finished_ok)
        self.gpu_install_thread.failed.connect(self.gpu_install_failed)
        # Jobs would pick up the half-installed environment.
        self.start_button.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.show()
        self.gpu_install_thread.start()

    @Slot()
    def gpu_install_finished_ok(self):
        self.start_button.setEnabled(True)
        self.progress_bar.hide()
        self.update_status("GPU acceleration environment installed.")
        QMessageBox.information(
            self, "GPU Acceleration",
            "GPU acceleration environment installed. See the status log "
            "for whether a CUDA GPU was actually detected.")

    @Slot(str)
    def gpu_install_failed(self, message):
        self.start_button.setEnabled(True)
        self.progress_bar.hide()
        self.update_status(f"GPU acceleration install failed: {message}")
        QMessageBox.critical(
            self, "GPU Acceleration",
            f"Installing the GPU acceleration environment failed:\n{message}")

    def start_process(self):
        url = self.browser.url().toString()
        if not (is_valid_video_url(url) or is_valid_playlist_url(url)):
            self.update_status(
                "Navigate to a YouTube video or playlist first, then click "
                f"{self.start_button.text()}.")
            return
        job = Job(url, page_title_to_job_title(self.browser.title()),
                  self.args.out, self.args.backend, self.args.model,
                  self.args.sample_rate)
        self.update_status(f"Queued {job.title}" if self.queue.busy
                           else f"Splitting the soundtrack of {job.title}")
        self.queue.add(job)

    def stop_process(self):
        self.stop_button.setEnabled(False)
        self.stop_button.setText("Stopping...")
        self.update_status("Stopping after the current step...")
        self.queue.stop_current()

    @Slot(bool)
    def busy_changed(self, busy):
        self.start_button.setText("Add to Queue" if busy else "Start")
        self.stop_button.setVisible(busy)
        self.stop_button.setEnabled(True)
        self.stop_button.setText("Stop")
        self.progress_bar.setVisible(busy)
        if busy:
            self.update_progress(-1)

    @Slot(object)
    def job_added(self, job):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, job)
        self.job_list.addItem(item)
        self.job_items[job] = item
        self.render_job(job)

    @Slot(object)
    def job_removed(self, job):
        item = self.job_items.pop(job)
        self.job_list.takeItem(self.job_list.row(item))

    @Slot(object)
    def job_changed(self, job):
        self.render_job(job)
        if job.state == DONE:
            self.update_status(f"Done: {job.title}"
                               + (f" ({job.message})" if job.message else "")
                               + ". Stems written to:")
            for path in job.outputs:
                self.append_link(path)
            if not job.outputs:
                self.append_link(job.out_dir)
        elif job.state == FAILED:
            print(f"Extraction failed: {job.message}", file=sys.stderr)
            self.update_status(f"Failed: {job.title}: {job.message}")
        elif job.state == CANCELLED:
            self.update_status(f"Stopped: {job.title}")

    def render_job(self, job):
        item = self.job_items[job]
        text = f"{JOB_STATE_LABELS[job.state]}: {job.title}"
        if job.finished and job.message:
            text += f" ({job.message})"
        item.setText(text)
        tooltip = [job.url, f"Output folder: {job.out_dir}",
                   f"Backend: {job.backend}" + (f" ({job.model})" if job.model else "")]
        if job.sample_rate:
            tooltip.append(f"Sample rate: {job.sample_rate} Hz")
        tooltip += job.outputs
        item.setToolTip("\n".join(tooltip))
        icon = {
            RUNNING: QStyle.SP_MediaPlay,
            DONE: QStyle.SP_DialogApplyButton,
            FAILED: QStyle.SP_MessageBoxCritical,
            CANCELLED: QStyle.SP_MediaStop,
        }.get(job.state)
        if icon is not None:
            item.setIcon(self.style().standardIcon(icon))
        else:
            # A blank icon keeps queued jobs' text aligned with the others'.
            blank = QPixmap(self.job_list.iconSize())
            blank.fill(Qt.transparent)
            item.setIcon(QIcon(blank))

    def show_job_menu(self, pos):
        item = self.job_list.itemAt(pos)
        job = item.data(Qt.UserRole) if item else None
        menu = QMenu(self)
        if job is not None and job.state == QUEUED:
            menu.addAction("Remove from Queue", lambda: self.queue.remove(job))
        if job is not None and job.state == RUNNING:
            menu.addAction("Stop", self.stop_process)
        if job is not None and job.finished:
            menu.addAction("Open Output Folder",
                           lambda: self.open_output_folder(job.out_dir))
        if job is not None:
            menu.addAction("Open in Browser",
                           lambda: self.browser.setUrl(QUrl(job.url)))
        if any(j.finished for j in self.queue.jobs):
            menu.addSeparator()
            menu.addAction("Clear Finished Jobs", self.queue.clear_finished)
        if not menu.isEmpty():
            menu.exec(self.job_list.viewport().mapToGlobal(pos))

    def job_double_clicked(self, item):
        job = item.data(Qt.UserRole)
        if job.finished:
            self.open_output_folder(job.out_dir)

    def _status_cursor(self):
        cursor = self.status_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.status_output.document().isEmpty():
            cursor.insertBlock()
        # Plain text: don't carry a previous link's formatting over.
        cursor.setCharFormat(QTextCharFormat())
        return cursor

    def _scroll_status_to_end(self):
        bar = self.status_output.verticalScrollBar()
        bar.setValue(bar.maximum())

    @Slot(str)
    def update_status(self, message):
        # insertText rather than append(): messages are plain text, even
        # when they happen to look like HTML.
        self._status_cursor().insertText(message)
        self._scroll_status_to_end()

    def append_link(self, path):
        """Appends a clickable path to the status log."""
        url = QUrl.fromLocalFile(path).toString()
        self._status_cursor().insertHtml(
            f'&nbsp;&nbsp;<a href="{html.escape(url)}">{html.escape(path)}</a>')
        self._scroll_status_to_end()

    @Slot()
    def url_changed(self):
        self.browser.setUrl(self.url_input.text())

    @Slot(int)
    def update_progress(self, value):
        if value < 0:
            self.progress_bar.setRange(0, 0)  # busy, no estimate
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)

    def closeEvent(self, event):
        gpu_installing = (self.gpu_install_thread is not None
                          and self.gpu_install_thread.isRunning())
        if not (self.queue.busy or gpu_installing):
            event.accept()
            return
        answer = QMessageBox.question(
            self, "Quit Yaas?",
            ("The GPU acceleration environment is still being installed."
             if gpu_installing else
             "A job is still running. It will be stopped, and the queued "
             "jobs dropped.")
            + " Quit anyway?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            event.ignore()
            return
        if gpu_installing or not self.queue.shutdown(10000):
            # A step that can't be interrupted (or the GPU install) is still
            # running, and Qt aborts when a running QThread is destroyed.
            # Leave right away instead; the job's intermediate files are
            # cleaned up on the next start.
            os._exit(0)
        event.accept()

    def check_ffmpeg(self):
        # Try to call ffmpeg and capture the result
        try:
            result = subprocess.run(["ffmpeg", "-version"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            if result.returncode != 0:
                self.show_popup("FFMPEG is not available. "
                                "Please install it before starting Yaas.")
        except FileNotFoundError:
            self.show_popup("FFMPEG is not available. "
                            "Please install it before starting Yaas.")
        except Exception as e:
            self.show_popup(f"Error occurred: {e}")

    def show_popup(self, message):
        # Create a popup message box
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(message)
        msg_box.setWindowTitle("FFMPEG Check")
        msg_box.exec()
        sys.exit(1)


def main():
    # Runs, and exits, when this process is one of the separation's child
    # processes in a frozen app (see local_extraction.py). pyinstmain.py
    # calls it already, sooner; this covers other frozen entry points.
    multiprocessing.freeze_support()
    if "--self-test" in sys.argv:
        # Headless packaging smoke test, run by release.yml on each built
        # installer; see self_test.py.
        from . import self_test
        i = sys.argv.index("--self-test")
        report = sys.argv[i + 1] if len(sys.argv) > i + 1 else None
        sys.exit(self_test.run(report))
    # Before creating any window, so --help and --version just print.
    args = parse_args()
    # 1. Platform-Specific Fixes
    if sys.platform.startswith("linux"):
        # Only force X11/xcb on Linux to bypassWayland Chromium bugs
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        # Optional: ONLY use this if Linux users experience crashes without it.
        # Try to keep it commented out for maximum user security.
        # os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
        # The frozen/AppImage build bundles its own libibusplatforminputcontextplugin.so.
        # On a desktop that runs ibus-daemon (the Ubuntu/GNOME default, even for
        # plain Latin keyboard layouts), Qt lazily loads and connects that plugin
        # to the *system* ibus-daemon the first time a text field requests an
        # input context -- i.e. on the first keystroke typed anywhere, including
        # into the embedded YouTube page. The bundled plugin talking to whatever
        # ibus happens to be installed on the user's system is a well-known
        # source of crashes for frozen/bundled Qt apps. Disabling platform IME
        # integration entirely avoids loading that plugin at all; basic (Latin)
        # text entry still works fine without it.
        os.environ["QT_IM_MODULE"] = ""
    # 2. Safe Cross-Platform Flags (Windows, Mac, and Linux)
    # Fixes the YouTube rendering flicker cleanly across all OS environments
    # sys.argv.append("--disable-gpu-compositing")

    # Forces proper graphics communication in Qt6
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(icon_path()))

    main_window = MainWindow(args)
    main_window.check_ffmpeg()
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
