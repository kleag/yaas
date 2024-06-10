"""yturl2mp3.config: Configuration settings object"""


class Config:
    """The configuration settings for downloading a video."""

    def __init__(self, out_dir: str, timeout: int, max_retries: int) -> None:
        """
        Constructor

        :param out_dir: The directory in which to store the downloaded MP3 files.
        :param timeout: Request timeout length in seconds
        :param max_retries: Number of retries on failed download
        """
        self.out_dir: str = out_dir
        self.timeout: int = timeout
        self.max_retries: int = max_retries
