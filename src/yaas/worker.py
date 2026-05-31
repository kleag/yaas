import argparse
import sys
import os
import logging
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
try:
    from audio_separator.separator import Separator
    HAS_AUDIO_SEPARATOR = True
except ImportError:
    HAS_AUDIO_SEPARATOR = False


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
        self.backend_type = getattr(yaas.args, 'backend', 'openunmix')  # Default to openunmix
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

                video = YouTube(url)
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
        if self.backend_type == "audio_separator":
            if not HAS_AUDIO_SEPARATOR:
                self.extraction_failed.emit("audio_separator library not installed. Please install it with 'pip install \"audio_separator[cpu]\"'")
                return
            self._extract_with_audio_separator(flac_path)
        else:
            # Default to openunmix
            self._extract_with_openunmix(flac_path)
        self.extraction_done.emit()

    def _extract_with_openunmix(self, flac_path):
        self.update_status.emit(f"Extracting tracks from flac {flac_path} with OpenUnmix...")
        try:
            # Load the model
            model = openunmix.umxl()
        except BaseException as ex:
            self.extraction_failed.emit(f"Loading model failed with: {str(ex)}")
            raise
        try:
            # Load the audio file
            waveform, sample_rate = torchaudio.load(flac_path)
            waveform = waveform.mean(dim=0, keepdim=True)  # Convert to mono
            print(f"Loaded audio at: {sample_rate}MHz", file=sys.stderr)
            self.update_status.emit(f"Loaded audio at: {sample_rate}MHz")

        except BaseException as ex:
            self.extraction_failed.emit(f"Converting to mono failed with: {str(ex)}")
            raise
        try:

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
        except BaseException as ex:
            self.extraction_failed.emit(f"Source separation failed with: {str(ex)}")
            raise
        try:

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
        except BaseException as ex:
            self.extraction_failed.emit(f"Saving extracted tracks failed with: {str(ex)}")
            raise

    def _extract_with_audio_separator(self, flac_path):
        self.update_status.emit(f"Extracting tracks from flac {flac_path} with audio_separator...")
        try:
            # Initialize audio separator
            separator = Separator(
                log_level=logging.INFO,
                output_dir=self.out,
                output_format="WAV",
            )
            
            # Load a specific RoFormer model trained for multi-stem
            separator.load_model(model_filename="BS-Roformer-SW.ckpt")
            # separator.load_model(model_filename="htdemucs_6s.yaml")


            
            # Separate audio
            output_files = separator.separate(flac_path)
            
            # Process output files - audio_separator generates files in output directory
            self.update_status.emit(f"Separation complete. Generated files: {output_files}")
            
        except Exception as ex:
            self.extraction_failed.emit(f"Audio separator failed with: {str(ex)}")
            raise
