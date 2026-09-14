"""yturl2mp3.helpers: Helper functions and classes for the main yturl2mp3 program."""


from .config import Config
import re
import os
from pydub import AudioSegment
from pytubefix import YouTube

YOUTUBE_URL = 'https://www.youtube.com'


def download_mp3(video: YouTube, config: Config) -> str:
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

    path_to_saved = stream.download(
        output_path=config.out_dir, timeout=config.timeout,
        max_retries=config.max_retries,
        skip_existing=True)
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


def is_valid_video_url(url: str) -> bool:
    """
    Determines if the url is a valid YouTube video link

    Example of a valid url:
        `https://www.youtube.<COUNTRY_CODE>/watch?v=<VIDEO_ID>`

    :param url: The url pointing to the YouTube video
    :return: True if the url is valid, otherwise false
    """
    # return None is not re.match('https:\/\/www\.youtube\.[a-z]{2,}\/watch\?v=([A-Za-z0-9-_\&]+)', url)
    # 1. We anchor the end ($) so extra parameters don't break the logic
    # 2. We limit the video ID to exactly 11 characters {11}
    pattern = r'^https://www\.youtube\.[a-z]{2,}/watch\?v=([A-Za-z0-9_-]{11})'

    return bool(re.match(pattern, url))

def is_valid_playlist_url(url: str) -> bool:
    """
    Determines if the url is a valid YouTube playlist link

    Example of a valid url:
        `https://www.youtube.<COUNTRY_CODE>/playlist?list=<PLAYLIST_ID>`

    :param url: The url to validate
    :return: True if the url is valid, otherwise false.
    """
    # return None is not re.match('https:\/\/www\.youtube\.[a-z]{2,}\/playlist\?list=([A-Za-z0-9-_\&]+)', url)
    pattern = r'^https://www\.youtube\.[a-z]{2,}/playlist\?list=([A-Za-z0-9-_\&]+)'

    return bool(re.match(pattern, url))
