"""yturl2mp3.helpers: Helper functions and classes for the main yturl2mp3 program."""


from .config import Config
import re
import os
from moviepy import editor
from pytube import YouTube


YOUTUBE_URL = 'https://www.youtube.com'


def download_mp3(video: YouTube, config: Config) -> str:
    """
    Downloads the audio of a YouTube video in MP3 format.

    :param video: The video from which to download the audio
    :param config: The configuration settings for the download
    :return: The path of the newly created mp4 file
    """
    # returns the mp4 only containing audio
    stream = video.streams.get_lowest_resolution()
    stream.download(output_path=config.out_dir, timeout=config.timeout, max_retries=config.max_retries,
                    skip_existing=True)
    mp4_path = config.out_dir + '/' + stream.default_filename
    return mp4_path


def convert_mp4_to_mp3(path: str, delete_after: bool = True) -> str:
    """
    Converts an mp4 file to an mp3 file

    :param path: The path of the mp4 file
    :param delete_after: If false, the mp4 file will not be deleted after conversion
    :return: The path of the newly created mp3 file
    """
    mp3_path = f'{path[:-3]}mp3'  # changes "mp4" to "mp3"
    mp4 = editor.VideoFileClip(path)

    mp3 = mp4.audio
    mp3.write_audiofile(mp3_path)

    mp3.close()
    mp4.close()

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
    return None is not re.match('https:\/\/www\.youtube\.[a-z]{2,}\/watch\?v=([A-Za-z0-9-_\&]+)', url)


def is_valid_playlist_url(url: str) -> bool:
    """
    Determines if the url is a valid YouTube playlist link

    Example of a valid url:
        `https://www.youtube.<COUNTRY_CODE>/playlist?list=<PLAYLIST_ID>`

    :param url: The url to validate
    :return: True if the url is valid, otherwise false.
    """
    return None is not re.match('https:\/\/www\.youtube\.[a-z]{2,}\/playlist\?list=([A-Za-z0-9-_\&]+)', url)
