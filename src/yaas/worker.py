import argparse
import sys
import os
from PySide6.QtCore import (QThread, Signal, QStandardPaths, QDir)
from pytubefix import YouTube, Playlist
from pydub import AudioSegment
import torch
import torchaudio
import os
import openunmix
from openunmix.predict import separate
from yturl2mp3.config import Config
from yturl2mp3.helpers import (convert_mp4_to_mp3, download_mp3,
                               is_valid_playlist_url, is_valid_video_url)


class Worker(QThread):
    update_status = Signal(str)
    ex_exit = Signal(BaseException, int)
    extraction_done = Signal()
    extraction_failed = Signal(str)

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
        self.convert_to_flac(mp3_path, flac_path)
        self.update_status.emit(f"Converted to FLAC: {flac_path}")
        os.remove(mp3_path)
        self.update_status.emit("Extracting tracks...")
        self.extract_tracks(flac_path)
        self.update_status.emit("Extraction complete")
        os.remove(flac_path)

    def download_audio(self, url):
        self.update_status.emit(f"Downloading audio from {url} ...")
        filename = ""
        try:
            if is_valid_video_url(url):
                self.update_status.emit(
                    'Single YouTube video Detected. Initializing...')

                video = YouTube(url)
                config = Config(out_dir=self.app_data_path, timeout=5000,
                                max_retries=3)
                self.update_status.emit(f"Downloading audio to {self.app_data_path} ...")
                path = download_mp3(video, config)

                self.update_status.emit(f'Converting video {path} to MP3 File...')

                filename = convert_mp4_to_mp3(path)

                self.update_status.emit(f'Conversion complete... Result: {filename}')
            elif is_valid_playlist_url(url):
                self.update_status.emit(
                    'YouTube playlist Detected. Initializing...')

                playlist = Playlist(url)
                for i, video in enumerate(playlist.videos):
                    path = download_mp3(video, config)

                    self.update_status.emit(
                        f'Converting video {i} to MP3 File...')

                    filename = convert_mp4_to_mp3(path)

                    self.update_status.emit(
                        'Conversion complete. Moving on to next...')
                self.update_status.emit(f'All videos converted.')
            else:
                self.extraction_failed.emit(
                    'The given url is not a valid YouTube link')
        except BaseException as ex:
            self.extraction_failed.emit(f"Downloading audio failed with: {str(ex)}")

        return filename

    def convert_to_flac(self, mp3_path, flac_path):
        self.update_status.emit(f"Converting mp3 {mp3_path} to flac {flac_path}...")
        try:
            audio = AudioSegment.from_mp3(mp3_path)
            audio.export(flac_path, format="flac")
        except BaseException as ex:
            self.extraction_failed.emit(f"Conversion to flac failed: {str(ex)}")

    def extract_tracks(self, flac_path):
        self.update_status.emit(f"Extracting tracks from flac {flac_path}...")
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
                # Extract the file name without the extension
                file_name = os.path.splitext(os.path.basename(flac_path))[0]
                # Create the new path
                wav_path = os.path.join(self.out, f"{file_name}_{source}.wav")

                self.update_status.emit(f'Writing result to {wav_path}')
                torchaudio.save(
                    wav_path,
                    torch.squeeze(estimate).to("cpu"),
                    sample_rate= sample_rate,
                )
                self.update_status.emit(f'Wrote {source} to {wav_path}')
            self.extraction_done.emit()
        except BaseException as ex:
            self.extraction_failed.emit(f"Tracks extraction failed with: {str(ex)}")


