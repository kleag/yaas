import argparse
import os
import subprocess
import sys


def _add_macos_package_manager_paths():
    """macOS apps launched from Finder/the Dock (like the dmg's yaas.app)
    don't inherit the user's shell PATH: they get only
    /usr/bin:/bin:/usr/sbin:/sbin, so an ffmpeg installed with Homebrew or
    MacPorts is never found even though it works in a terminal. Add their
    standard bin directories. This must run before pydub is imported (via
    .worker below), since pydub looks ffmpeg up once at import time."""
    if sys.platform != "darwin":
        return
    path = os.environ.get("PATH", "").split(os.pathsep)
    extra = [d for d in ("/opt/homebrew/bin",  # Homebrew, Apple Silicon
                         "/usr/local/bin",     # Homebrew, Intel
                         "/opt/local/bin")     # MacPorts
             if os.path.isdir(d) and d not in path]
    os.environ["PATH"] = os.pathsep.join(extra + path)


_add_macos_package_manager_paths()

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTextEdit, QMessageBox, QSizePolicy,
                               QProgressBar, QToolButton, QMenu, QDialog,
                               QFormLayout, QDialogButtonBox, QFileDialog)
from PySide6.QtCore import (Qt, QStandardPaths, QThread, QUrl, Signal, Slot)
from PySide6.QtGui import QDesktopServices, QIcon

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from typing import NoReturn

from . import __version__
from . import gpu_env
from . import settings
from .worker import Worker

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
        self.accept()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        initial_url= "https://www.youtube.com"
        self.args = self.parse_args()
        if not self.args.out:
            self.args.out = settings.get_output_dir()

        self.setWindowTitle("YouTube Audio Splitter")
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

        self.main_menu = QMenu(self.menu_button)
        self.main_menu.addAction("Settings...", self.open_settings_dialog)
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
        self.layout.addWidget(self.browser)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_process)
        self.layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_process)
        self.layout.addWidget(self.stop_button)
        self.stop_button.hide()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)
        self.progress_bar.hide()

        self.status_output = QTextEdit()
        self.status_output.setReadOnly(True)
        self.status_output.setFixedHeight(70)  # Approximately 3 lines
        self.layout.addWidget(self.status_output)

        self.setLayout(self.layout)


    def setup_persistent_profile(self):
        # Create a custom profile with a persistent storage path
        storage_path = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        storage_path = os.path.realpath(storage_path)
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
        if clicked == install_button:
            self.confirm_and_install_gpu_env()
        elif remove_button is not None and clicked == remove_button:
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
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.gpu_install_thread.start()

    @Slot()
    def gpu_install_finished_ok(self):
        self.progress_bar.hide()
        self.update_status("GPU acceleration environment installed.")
        QMessageBox.information(
            self, "GPU Acceleration",
            "GPU acceleration environment installed. See the status log "
            "above for whether a CUDA GPU was actually detected.")

    @Slot(str)
    def gpu_install_failed(self, message):
        self.progress_bar.hide()
        self.update_status(f"GPU acceleration install failed: {message}")
        QMessageBox.critical(
            self, "GPU Acceleration",
            f"Installing the GPU acceleration environment failed:\n{message}")

    def parse_args(self) -> argparse.Namespace:
        """
        Parse the command line arguments

        :return: The parsed argument namespace
        """
        description = 'Youtube To MP3 Download Tool'
        parser = argparse.ArgumentParser(description=description)

        parser.add_argument(
            '-o', '--out', metavar="DIR", type=str,
            default=None,
            help="The directory in which to store the downloaded MP3 files. "
                 "Overrides the Settings dialog's output folder for this run "
                 "only; defaults to it if not given.")
        
        parser.add_argument(
            '--backend', metavar="BACKEND", type=str,
            default="audio_separator",
            choices=["audio_separator", "openunmix"],
            help="The backend to use for track separation (openunmix, audio_separator)")
        
        parser.add_argument(
            '--model', metavar="MODEL", type=str,
            default="roformer",
            choices=["roformer", "htdemucs6s"],
            help="The model to use with audio_separator backend (roformer, htdemucs6s)")

        return parser.parse_known_args()[0]

    def start_process(self):
        # url = self.url_input.text()
        url = self.browser.url().url()
        if url:
            self.update_status(f"Splitting sound track of {url}")
            self.worker = Worker(url, self)
            self.worker.ex_exit.connect(self.ex_exit)
            # Change the cursor to busy
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.worker.extraction_done.connect(self.extraction_done)
            self.worker.extraction_failed.connect(self.extraction_failed)
            self.worker.progress.connect(self.update_progress)
            self.progress_bar.setRange(0, 0)  # indeterminate until real progress arrives
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self.worker.start()
            self.start_button.hide()
            self.stop_button.show()

    def stop_process(self):
        # Restore the cursor to normal
        QApplication.restoreOverrideCursor()
        self.worker.terminate()
        self.start_button.show()
        self.stop_button.hide()
        self.progress_bar.hide()

    def update_status(self, message):
        self.status_output.append(message)

    def ex_exit(self, ex: BaseException, exit_code: int = 1) -> NoReturn:
        """
        Exit with an exception

        :param ex: The exception being thrown
        :param exit_code: The exit code of the program
        """
        QMessageBox.critical(
                    self,
                    "Fatal Error",
                    f"Exception: {ex}.")
        sys.exit(exit_code)

    @Slot()
    def url_changed(self):
        self.browser.setUrl(self.url_input.text())

    @Slot()
    def extraction_done(self):
        # Restore the cursor to normal
        QApplication.restoreOverrideCursor()
        self.start_button.show()
        self.stop_button.hide()
        self.progress_bar.hide()

        # Optional: Notify the user that the operation has finished
        self.update_status("Extraction done")

    @Slot()
    def extraction_failed(self, message: str):
        # Restore the cursor to normal
        QApplication.restoreOverrideCursor()
        self.start_button.show()
        self.stop_button.hide()
        self.progress_bar.hide()

        # Optional: Notify the user that the operation has finished
        print(f"Extraction failed: {message}", file=sys.stderr)
        self.update_status(f"Extraction failed: {message}")

    @Slot(int)
    def update_progress(self, value):
        if self.progress_bar.maximum() == 0:
            # Switch out of indeterminate/busy mode once real progress arrives.
            self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)


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

    main_window = MainWindow()
    main_window.check_ffmpeg()
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
