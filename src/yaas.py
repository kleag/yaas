import argparse
import os
import sys

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTextEdit,
                               QMessageBox, QSizePolicy)
from PySide6.QtCore import (Qt, Slot)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from typing import NoReturn

from worker import Worker

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        initial_url= "https://www.youtube.com"
        self.args = self.parse_args()

        self.setWindowTitle("YouTube Audio Splitter")
        self.setGeometry(100, 100, 1024, 768)

        self.layout = QVBoxLayout()

        self.label = QLabel("Enter YouTube URL:")
        self.layout.addWidget(self.label)

        self.url_input = QLineEdit(initial_url)
        self.layout.addWidget(self.url_input)
        self.url_input.editingFinished.connect(self.url_changed)

        self.browser = QWebEngineView()
        self.browser.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.browser.setUrl(initial_url)
        self.browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.browser.urlChanged.connect(self.update_line_edit)
        self.layout.addWidget(self.browser)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_process)
        self.layout.addWidget(self.start_button)

        self.status_output = QTextEdit()
        self.status_output.setReadOnly(True)
        self.status_output.setFixedHeight(70)  # Approximately 3 lines
        self.layout.addWidget(self.status_output)

        self.setLayout(self.layout)


    def update_line_edit(self, url):
        # Convert QUrl to string and set the text of QLineEdit
        self.url_input.setText(url.toString())

    def parse_args(self) -> argparse.Namespace:
        """
        Parse the command line arguments

        :return: The parsed argument namespace
        """
        description = 'Youtube To MP3 Download Tool'
        parser = argparse.ArgumentParser(description=description)

        parser.add_argument(
            '-o', '--out', metavar="DIR", type=str, default='mp3',
            help="The directory in which to store the downloaded MP3 files.")

        return parser.parse_args()


    def start_process(self):
        # url = self.url_input.text()
        url = self.browser.url().url()
        if url:
            self.update_status(f"Splitting sound track of {url}")
            self.worker = Worker(url, self.args.out)
            self.worker.update_status.connect(self.update_status)
            self.worker.ex_exit.connect(self.ex_exit)
            # Change the cursor to busy
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.worker.extraction_done.connect(self.extraction_done)
            self.worker.extraction_failed.connect(self.extraction_failed)
            self.worker.start()

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

        # Optional: Notify the user that the operation has finished
        self.update_status("Extraction done")

    @Slot()
    def extraction_failed(self, message: str):
        # Restore the cursor to normal
        QApplication.restoreOverrideCursor()

        # Optional: Notify the user that the operation has finished
        print(f"Extraction failed: {message}", file=sys.stderr)
        self.update_status(f"Extraction failed: {message}")



def main():
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
