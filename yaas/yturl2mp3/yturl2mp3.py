"""ytmp3.yturl2mp3: provides entry point main()."""

__version__ = "0.4.1"

import sys
import os
import argparse
import colorama
from colorama import Fore
from typing import NoReturn
from .config import Config
from .helpers import convert_mp4_to_mp3, download_mp3, is_valid_playlist_url, is_valid_video_url
from pytube import YouTube, Playlist

colorama.init()


def main() -> None:
    """The main function of the script"""
    args = parse_args()
    url = args.url

    config = Config(out_dir=args.out, timeout=args.timeout,
                    max_retries=args.retry)

    try:
        if not os.path.exists(config.out_dir):
            os.mkdir(config.out_dir)
            log_info('Output directory created')

        if is_valid_video_url(url):
            log_info('Single YouTube video Detected. Initializing...')

            video = YouTube(url)
            path = download_mp3(video, config)
            
            log_info('Converting video to MP3 File...')
            
            convert_mp4_to_mp3(path)
            
            log_info('Conversion complete...')
        elif is_valid_playlist_url(url):
            log_info('YouTube playlist Detected. Initializing...')
            
            playlist = Playlist(url)
            for video in playlist.videos:
                path = download_mp3(video, config)

                log_info('Converting video to MP3 File...')
                
                convert_mp4_to_mp3(path)
                
                log_info('Conversion complete. Moving on to next...')
            log_info(f'All videos converted. Enjoy your new MP3 files in {config.out_dir}!')
        else:
            raise ValueError('The given url is not a valid YouTube link')
    except BaseException as ex:
        ex_exit(ex, 1)


def log_info(msg: str) -> None:
    """
    Logs an informational message to the console

    :param msg: The message to log
    """
    print(Fore.YELLOW, '[youtube-to-mp3] ', Fore.BLUE, msg, sep="")


def ex_exit(ex: BaseException, exit_code: int = 1) -> NoReturn:
    """
    Exit with an exception

    :param ex: The exception being thrown
    :param exit_code: The exit code of the program
    """
    print(Fore.YELLOW, '[youtube-to-mp3] ', Fore.RED, ex.__class__.__name__, Fore.YELLOW, ': ', ex,
          file=sys.stderr, sep='')
    sys.exit(exit_code)


def parse_args() -> argparse.Namespace:
    """
    Parse the command line arguments

    :return: The parsed argument namespace
    """
    description = Fore.YELLOW + 'Youtube To MP3 Download Tool'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('url', metavar='URL', type=str,
                        help="The YouTube URL to download. Playlist or single video.")

    parser.add_argument('-o', '--out', metavar="DIR", type=str, default='mp3',
                        help="The directory in which to store the downloaded MP3 files.")

    parser.add_argument('-t', '--timeout', metavar='S', type=int, default=5000,
                        help="Request timeout length in seconds")

    parser.add_argument('-r', '--retry', metavar="N", type=int, default=3,
                        help="Number of retries on failed download")

    return parser.parse_args()