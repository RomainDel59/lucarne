"""YouTube input boundary tests."""

import pytest

from src.assets import ALLOWED_IMAGE_HOSTS
from src.errors import LucarneError
from src.youtube import normalize_channel_url, normalize_playlist_url, normalize_video_url, quality_format


def test_normalize_channel_url() -> None:
    assert normalize_channel_url("https://www.youtube.com/@example") == "https://www.youtube.com/@example/videos"


def test_normalize_video_url_strips_unrelated_parameters() -> None:
    assert (
        normalize_video_url("https://www.youtube.com/watch?v=abcdefghijk&t=30")
        == "https://www.youtube.com/watch?v=abcdefghijk"
    )


def test_normalize_playlist_url() -> None:
    assert (
        normalize_playlist_url("https://youtube.com/playlist?list=PLabcdefghijk123")
        == "https://www.youtube.com/playlist?list=PLabcdefghijk123"
    )


@pytest.mark.parametrize(
    "value",
    [
        "http://www.youtube.com/watch?v=abcdefghijk",
        "https://example.org/watch?v=abcdefghijk",
        "https://www.youtube.com/embed/abcdefghijk",
    ],
)
def test_reject_unsafe_video_urls(value: str) -> None:
    with pytest.raises(LucarneError):
        normalize_video_url(value)


def test_video_format_applies_both_video_and_audio_quality() -> None:
    value = quality_format("720", "128")

    assert "height<=720" in value
    assert "abr<=128" in value
    assert "vcodec^=avc1" in value


def test_audio_quality_of_64_kbps_is_supported() -> None:
    assert "abr<=64" in quality_format("720", "64")


def test_both_youtube_channel_image_hosts_are_allowed() -> None:
    assert {"yt3.ggpht.com", "yt3.googleusercontent.com"} <= ALLOWED_IMAGE_HOSTS
