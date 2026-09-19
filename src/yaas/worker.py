import argparse
import sys
import os
from PySide6.QtCore import (QThread, Signal, QStandardPaths, QDir)
from pytubefix import YouTube, Playlist
from pydub import AudioSegment
from yturl2mp3.config import Config
from yturl2mp3.helpers import (convert_mp4_to_mp3, download_mp3,
                               is_valid_playlist_url, is_valid_video_url)
from . import gpu_env
from .separate_worker import (HAS_AUDIO_SEPARATOR, extract_with_audio_separator,
                              extract_with_openunmix)


class Worker(QThread):
    update_status = Signal(str)
    ex_exit = Signal(BaseException, int)
    extraction_done = Signal()
    extraction_failed = Signal(str)
    progress = Signal(int)

    def __init__(self, url, yaas):
        super().__init__()
        self.update_status.connect(yaas.update_status)
        # Get the writable location for application data
        self.app_data_path = QStandardPaths.writableLocation(
            QStandardPaths.AppDataLocation)

        # Ensure the directory exists
        QDir().mkpath(self.app_data_path)
        self.update_status.emit(f'Created app_data_path {self.app_data_path}')
        print(f'Created app_data_path {self.app_data_path}', file=sys.stderr)

        self.url = url
        self.out = yaas.args.out
        self.backend_type = getattr(yaas.args, 'backend', 'openunmix')  # Default to openunmix
        self.model_type = getattr(yaas.args, 'model', 'roformer')  # Default to BS-Roformer-SW.ckpt
        self.gpu_env_dir = os.path.join(self.app_data_path, gpu_env.GPU_ENV_DIRNAME)
        if not QDir().mkpath(self.out):
            self.update_status.emit(f"Failed to creat result dir {self.out}")
            raise RuntimeError(f"Failed to creat result dir {self.out}")
        else:
            self.update_status.emit(f'Created result dir {self.out}')

    def run(self):
        mp3_path = self.download_audio(self.url)
        if not mp3_path:
            self.update_status.emit(f"Failed to download {self.url}")
            return
        self.update_status.emit(f"Downloaded: {mp3_path}")

        flac_path = mp3_path.replace('.mp3', '.flac')
        self.update_status.emit(f"Converting {mp3_path} to {flac_path}...")
        try:
            self.convert_to_flac(mp3_path, flac_path)
            self.update_status.emit(f"Converted to FLAC: {flac_path}")
            os.remove(mp3_path)
            self.update_status.emit("Extracting tracks...")
            self.extract_tracks(flac_path)
            self.update_status.emit("Extraction complete")
            os.remove(flac_path)
        except Exception:
            self.update_status.emit(f"Something went wrong during extraction "
                                    f"of {self.url}")
            return

    def download_audio(self, url):
        self.update_status.emit(f"Downloading audio from {url} ...")
        filename = ""
        try:
            if is_valid_video_url(url):
                self.update_status.emit(
                    'Single YouTube video Detected. Initializing...')

                video = YouTube(url, "WEB")
                config = Config(out_dir=self.app_data_path, timeout=5000,
                                max_retries=3)
                self.update_status.emit(f"Downloading audio to {self.app_data_path} ...")
                path = download_mp3(video, config)

                self.update_status.emit(f'Converting video {path} to MP3 File...')

                filename = convert_mp4_to_mp3(path, delete_after=True)

                self.update_status.emit(f'Conversion complete... Result: {filename}')
            elif is_valid_playlist_url(url):
                self.update_status.emit(
                    'YouTube playlist Detected. Initializing...')

                playlist = Playlist(url)
                for i, video in enumerate(playlist.videos):
                    path = download_mp3(video, config)

                    self.update_status.emit(
                        f'Converting video {i} to MP3 File...')

                    filename = convert_mp4_to_mp3(path, delete_after=True)

                    self.update_status.emit(
                        'Conversion complete. Moving on to next...')
                self.update_status.emit(f'All videos converted.')
            else:
                self.extraction_failed.emit(
                    'The given url is not a valid YouTube link')
        except BaseException as ex:
            self.extraction_failed.emit(f"Downloading audio failed with: {str(ex)}")
            raise

        return filename

    def convert_to_flac(self, mp3_path, flac_path):
        self.update_status.emit(f"Converting mp3 {mp3_path} to flac {flac_path}...")
        try:
            audio = AudioSegment.from_mp3(mp3_path)
            audio.export(flac_path, format="flac")
        except BaseException as ex:
            self.extraction_failed.emit(f"Conversion to flac failed: {str(ex)}")
            raise

    def extract_tracks(self, flac_path):
        self.update_status.emit(f"Extracting tracks from flac {flac_path} with backend {self.backend_type}...")
        try:
            if gpu_env.status(self.gpu_env_dir) == "ready":
                self.update_status.emit("Using GPU-accelerated environment for extraction...")
                gpu_env.run_extraction(
                    self.gpu_env_dir, flac_path, self.out, self.backend_type,
                    self.model_type, self.update_status.emit, self.progress.emit)
            elif self.backend_type == "audio_separator":
                if not HAS_AUDIO_SEPARATOR:
                    self.extraction_failed.emit(
                        "audio_separator library not installed. Please install "
                        "it with 'pip install \"audio_separator[cpu]\"'")
                    return
                extract_with_audio_separator(
                    flac_path, self.out, self.model_type,
                    self.update_status.emit, self.progress.emit)
            else:
                # Default to openunmix
                extract_with_openunmix(
                    flac_path, self.out, self.update_status.emit, self.progress.emit)
        except BaseException as ex:
            self.extraction_failed.emit(f"Extraction failed with: {str(ex)}")
            raise
        self.extraction_done.emit()
