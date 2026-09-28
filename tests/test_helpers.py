import pytest

from yturl2mp3.helpers import is_valid_playlist_url, is_valid_video_url

VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VIDEO_ID}",
    f"https://www.youtube.com/watch?v={VIDEO_ID}&list=PL123&index=2",
    f"https://www.youtube.com/watch?app=desktop&v={VIDEO_ID}",
    f"https://www.youtube.fr/watch?v={VIDEO_ID}",
    f"https://www.youtube.co.uk/watch?v={VIDEO_ID}",
    f"https://m.youtube.com/watch?v={VIDEO_ID}",
    f"https://music.youtube.com/watch?v={VIDEO_ID}",
    f"https://youtube.com/watch?v={VIDEO_ID}",
    f"https://www.youtube.com/shorts/{VIDEO_ID}",
    f"https://www.youtube.com/live/{VIDEO_ID}",
    f"https://youtu.be/{VIDEO_ID}",
    f"https://youtu.be/{VIDEO_ID}?t=42",
])
def test_valid_video_urls(url):
    assert is_valid_video_url(url)
    assert not is_valid_playlist_url(url)


@pytest.mark.parametrize("url", [
    "",
    "https://www.youtube.com",
    "https://www.youtube.com/",
    "https://www.youtube.com/results?search_query=bass",
    "https://www.youtube.com/watch?v=short",
    "https://www.youtube.com/@SomeChannel",
    f"https://www.notyoutube.com/watch?v={VIDEO_ID}",
    f"https://www.youtube.com.evil.example/watch?v={VIDEO_ID}",
    f"ftp://www.youtube.com/watch?v={VIDEO_ID}",
])
def test_invalid_video_urls(url):
    assert not is_valid_video_url(url)


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/playlist?list=PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG",
    "https://music.youtube.com/playlist?list=OLAK5uy_abc",
    "https://www.youtube.com/playlist?si=xyz&list=PL123",
])
def test_valid_playlist_urls(url):
    assert is_valid_playlist_url(url)
    assert not is_valid_video_url(url)


def test_invalid_playlist_urls():
    assert not is_valid_playlist_url("https://www.youtube.com/playlist")
    assert not is_valid_playlist_url("https://www.youtube.com/feed/playlists")
