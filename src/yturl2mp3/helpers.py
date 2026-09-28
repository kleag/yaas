"""yturl2mp3.helpers: Helper functions and classes for the main yturl2mp3 program."""


from .config import Config
import re
import os
from pydub import AudioSegment
from pytubefix import YouTube

YOUTUBE_URL = 'https://www.youtube.com'

# www., m. and music.youtube.com, and country domains such as youtube.fr or
# youtube.co.uk.
_YOUTUBE_HOST = r'https?://(?:(?:www|m|music)\.)?youtube\.[a-z]{2,3}(?:\.[a-z]{2})?'
_VIDEO_ID = r'[A-Za-z0-9_-]{11}'
_VIDEO_URL_PATTERNS = [
    # watch?v=ID, possibly after other parameters (watch?app=desktop&v=ID)
    re.compile(rf'^{_YOUTUBE_HOST}/watch\?(?:[^#]*&)?v={_VIDEO_ID}'),
    re.compile(rf'^{_YOUTUBE_HOST}/(?:shorts|live|embed)/{_VIDEO_ID}'),
    re.compile(rf'^https?://youtu\.be/{_VIDEO_ID}'),
]
_PLAYLIST_URL_PATTERN = re.compile(
    rf'^{_YOUTUBE_HOST}/playlist\?(?:[^#]*&)?list=[A-Za-z0-9_-]+')


def download_audio(video: YouTube, config: Config) -> str:
    """
    Downloads the audio of a YouTube video.

    :param video: The video from which to download the audio
    :param config: The configuration settings for the download
    :return: The path of the newly downloaded audio/video file
    """
    # Prefer an audio-only stream: it's smaller and, unlike a progressive
    # (video+audio) stream, YouTube still reliably offers one even though
    # progressive streams have been phased out for most videos/clients.
    stream = video.streams.get_audio_only()
    if stream is None:
        stream = video.streams.get_lowest_resolution()
    if stream is None:
        raise RuntimeError(
            f"No downloadable audio or video stream found for {video.watch_url}")

    # Not skip_existing: an interrupted download leaves a partial file
    # behind, which would then be taken for a complete one.
    path_to_saved = stream.download(
        output_path=config.out_dir, timeout=config.timeout,
        max_retries=config.max_retries)
    if not path_to_saved:
        raise RuntimeError(f"Downloading {video.watch_url} was interrupted")
    return os.path.realpath(path_to_saved)


def convert_mp4_to_mp3(path: str, delete_after: bool = True) -> str:
    """
    Converts a downloaded audio/video file to an mp3 file.

    :param path: The path of the downloaded file (e.g. mp4 or m4a)
    :param delete_after: If false, the source file will not be deleted after conversion
    :return: The path of the newly created mp3 file
    """
    mp3_path = f'{os.path.splitext(path)[0]}.mp3'
    # pydub (via ffmpeg) decodes the audio track regardless of whether the
    # container also holds a video track, unlike moviepy's VideoFileClip
    # which requires one.
    audio = AudioSegment.from_file(path)
    audio.export(mp3_path, format="mp3")

    if delete_after:
        os.remove(path)
    return mp3_path


def convert_to_flac(path: str, flac_path: str) -> str:
    """
    Decodes a downloaded audio/video file (e.g. m4a) straight to a lossless
    FLAC file, without an intermediate lossy (mp3) encoding.

    :param path: The path of the downloaded file
    :param flac_path: The path of the FLAC file to write
    :return: flac_path
    """
    AudioSegment.from_file(path).export(flac_path, format="flac")
    return flac_path


def is_valid_video_url(url: str) -> bool:
    """
    Determines if the url is a valid YouTube video link

    Examples of valid urls:
        `https://www.youtube.<COUNTRY_CODE>/watch?v=<VIDEO_ID>`
        `https://www.youtube.com/shorts/<VIDEO_ID>`
        `https://youtu.be/<VIDEO_ID>`

    :param url: The url pointing to the YouTube video
    :return: True if the url is valid, otherwise false
    """
    return any(pattern.match(url) for pattern in _VIDEO_URL_PATTERNS)


def is_valid_playlist_url(url: str) -> bool:
    """
    Determines if the url is a valid YouTube playlist link

    Example of a valid url:
        `https://www.youtube.<COUNTRY_CODE>/playlist?list=<PLAYLIST_ID>`

    :param url: The url to validate
    :return: True if the url is valid, otherwise false.
    """
    return bool(_PLAYLIST_URL_PATTERN.match(url))
