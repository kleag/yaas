import argparse
import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTextEdit, QMessageBox)
from PySide6.QtCore import (Qt, QThread, Signal, Slot)
import subprocess
from pytube import YouTube, Playlist
from pydub import AudioSegment
import torch
import torchaudio
import os
import openunmix
from openunmix.predict import separate
from typing import NoReturn
from yturl2mp3.config import Config
from yturl2mp3.helpers import (convert_mp4_to_mp3, download_mp3,
                               is_valid_playlist_url, is_valid_video_url)


class Worker(QThread):
    update_status = Signal(str)
    ex_exit = Signal(BaseException, int)
    extraction_done = Signal()
    extraction_failed = Signal()

    def __init__(self, url, out):
        super().__init__()
        self.url = url
        self.out = out

    def run(self):
        self.update_status.emit("Downloading audio...")
        mp3_path = self.download_audio(self.url)
        if not mp3_path:
            return
        self.update_status.emit(f"Downloaded: {mp3_path}")

        flac_path = mp3_path.replace('.mp3', '.flac')
        self.update_status.emit(f"Converting {mp3_path} to {flac_path}...")
        self.convert_to_flac(mp3_path, flac_path)
        self.update_status.emit(f"Converted to FLAC: {flac_path}")

        self.update_status.emit("Extracting tracks...")
        self.extract_tracks(flac_path)
        self.update_status.emit("Extraction complete")

    def download_audio(self, url):
        filename = ""
        try:
            if not os.path.exists(self.out):
                os.mkdir(self.out)
                self.update_status.emit('Output directory created')

            if is_valid_video_url(url):
                self.update_status.emit('Single YouTube video Detected. Initializing...')

                video = YouTube(url)
                config = Config(out_dir=self.out, timeout=5000, max_retries=3)
                path = download_mp3(video, config)

                self.update_status.emit('Converting video to MP3 File...')

                filename = convert_mp4_to_mp3(path)

                self.update_status.emit('Conversion complete...')
            elif is_valid_playlist_url(url):
                self.update_status.emit('YouTube playlist Detected. Initializing...')

                playlist = Playlist(url)
                for video in playlist.videos:
                    path = download_mp3(video, config)

                    self.update_status.emit(f'Converting video {video} to MP3 File...')

                    filename = convert_mp4_to_mp3(path)

                    self.update_status.emit('Conversion complete. Moving on to next...')
                self.update_status.emit(
                    f'All videos converted. Enjoy your new MP3 files in {config.out_dir}!')
            else:
                raise ValueError('The given url is not a valid YouTube link')
        except BaseException as ex:
            self.ex_exit.emit(ex, 1)


        return filename

    def convert_to_flac(self, mp3_path, flac_path):
        try:
            audio = AudioSegment.from_mp3(mp3_path)
            audio.export(flac_path, format="flac")
        except BaseException as ex:
            self.ex_exit.emit(ex, 1)

    def extract_tracks(self, flac_path):
        try:
            # Load the model
            model = openunmix.umxl()

            # Load the audio file
            waveform, sample_rate = torchaudio.load(flac_path)
            waveform = waveform.mean(dim=0, keepdim=True)  # Convert to mono

            # Perform source separation
            estimates = separate(
                waveform,
                rate=44100,
                # model_str_or_path="umxl",
                # targets=None,
                # niter=1,
                # residual=False,
                # wiener_win_len=300,
                # aggregate_dict=None,
                # separator=None,
                # device=None,
                # filterbank="torch",
                )

            # Save each estimated source
            for source, estimate in estimates.items():
                output_path = f"{os.path.splitext(flac_path)[0]}_{source}.wav"
                torchaudio.save(
                    output_path,
                    torch.squeeze(estimate).to("cpu"),
                    sample_rate= sample_rate,
                )
            self.extraction_done.emit()
        except BaseException as ex:
            self.extraction_failed.emit()
            # self.ex_exit.emit(ex, 1)




class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.args = self.parse_args()

        self.setWindowTitle("YouTube Audio Splitter")
        self.setGeometry(100, 100, 400, 200)

        self.layout = QVBoxLayout()

        self.label = QLabel("Enter YouTube URL:")
        self.layout.addWidget(self.label)

        self.url_input = QLineEdit()
        self.layout.addWidget(self.url_input)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_process)
        self.layout.addWidget(self.start_button)

        self.status_output = QTextEdit()
        self.status_output.setReadOnly(True)
        self.layout.addWidget(self.status_output)

        self.setLayout(self.layout)


    def parse_args(self) -> argparse.Namespace:
        """
        Parse the command line arguments

        :return: The parsed argument namespace
        """
        description = 'Youtube To MP3 Download Tool'
        parser = argparse.ArgumentParser(description=description)

        parser.add_argument('-o', '--out', metavar="DIR", type=str, default='mp3',
                            help="The directory in which to store the downloaded MP3 files.")

        return parser.parse_args()


    def start_process(self):
        url = self.url_input.text()
        if url:
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
    def extraction_done(self):
        # Restore the cursor to normal
        QApplication.restoreOverrideCursor()

        # Optional: Notify the user that the operation has finished
        self.update_status("Extraction done")

    @Slot()
    def extraction_failed(self):
        # Restore the cursor to normal
        QApplication.restoreOverrideCursor()

        # Optional: Notify the user that the operation has finished
        self.update_status("Extraction failed")



def main():
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
