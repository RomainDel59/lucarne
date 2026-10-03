"""Restricted yt-dlp integration used by the catalogue agent and player."""

from __future__ import annotations

import json
import os
import random
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .errors import LucarneError, VideoUnavailableError, YtDlpError

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,32}$")
PLAYLIST_ID = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
CHANNEL_PATH = re.compile(r"^/(?:@[^/]+|channel/[A-Za-z0-9_-]+|c/[^/]+|user/[^/]+)(?:/videos)?$")
ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
METADATA_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Z]{2})?")
# Messages of yt-dlp that mean a video cannot be read, so it is skipped as if it did not exist. They are only
# looked for in English: the reason of a failure is always read in English, whatever the metadata language.
UNAVAILABLE_MARKERS = (
    "video unavailable",
    "private video",
    "this video is unavailable",
    "has been removed",
    "members-only content",
    "join this channel",
    "confirm your age",
    # Premieres and live events that have not started: the video cannot be read yet.
    "premieres in",
    "premiere will begin",
    "this live event will begin",
)
# Among them, those that go away by themselves: the video is announced and will be readable later.
TEMPORARY_MARKERS = ("premieres in", "premiere will begin", "this live event will begin")
RELEASE_DELAY = re.compile(r"\bin (?:about |approximately )?(\d+|an?|one) (minute|hour|day|week|month)s?\b")
# An announced start closer than this is looked at no sooner: the video is not readable at the very second.
MINIMUM_RELEASE_DELAY = 300
UNIT_SECONDS = {"minute": 60, "hour": 3600, "day": 86400, "week": 7 * 86400, "month": 30 * 86400}


def release_delay(reason: str) -> int | None:
    """Seconds before a premiere or a live event starts, when the message says it ("Premieres in 2 hours")."""
    match = RELEASE_DELAY.search(reason.lower())
    if not match:
        return None
    amount = int(match.group(1)) if match.group(1).isdigit() else 1
    return amount * UNIT_SECONDS[match.group(2)]


def is_temporary(reason: str) -> bool:
    return any(marker in reason.lower() for marker in TEMPORARY_MARKERS)


def classify_failure(video_id: str, error: LucarneError) -> dict[str, Any]:
    """Describe why a video could not be read: known or not, temporary or not, and when to try again.

    The start of a premiere is the exact time given by YouTube when it was asked for, else the delay read in the
    message, else nothing: the video is then looked at every hour.
    """
    reason = str(getattr(error, "reason", None) or error)
    known = isinstance(error, VideoUnavailableError)
    temporary = known and is_temporary(reason)
    retry_after = None
    if temporary:
        stamp = getattr(error, "release_timestamp", None)
        retry_after = (
            max(int(stamp) - int(time.time()), MINIMUM_RELEASE_DELAY) if stamp else release_delay(reason)
        )
    return {
        "id": video_id,
        "reason": reason[-2000:],
        "known": known,
        "temporary": temporary,
        "retry_after": retry_after,
    }


def video_id_from_url(value: str) -> str:
    """The identifier of a normalized video address."""
    return parse_qs(urlsplit(value).query).get("v", [""])[0]


def quality_format(quality: str, audio_quality: str) -> str:
    if audio_quality not in {"64", "96", "128", "192", "256"}:
        raise LucarneError("Invalid audio quality.")
    audio = f"ba[acodec^=mp4a][abr<={audio_quality}]"
    if quality == "best":
        return f"bv*[vcodec^=avc1]+{audio}/bv*[vcodec^=avc1]+ba/b[ext=mp4]/best"
    if quality not in {"360", "480", "720", "1080"}:
        raise LucarneError("Invalid video quality.")
    return (
        f"bv*[height<={quality}][vcodec^=avc1]+{audio}/"
        f"bv*[height<={quality}][vcodec^=avc1]+ba/"
        f"b[height<={quality}][ext=mp4]/best[height<={quality}]"
    )


def normalize_video_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    values = parse_qs(parsed.query).get("v", [])
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise LucarneError("Only HTTPS YouTube video URLs are allowed.")
    if parsed.path != "/watch" or len(values) != 1 or not VIDEO_ID.fullmatch(values[0]):
        raise LucarneError("The YouTube video URL is invalid.")
    return f"https://www.youtube.com/watch?v={values[0]}"


def normalize_channel_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    path = parsed.path.rstrip("/")
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() not in ALLOWED_HOSTS
        or CHANNEL_PATH.fullmatch(path) is None
    ):
        raise LucarneError("The YouTube channel URL is invalid.")
    if not path.endswith("/videos"):
        path += "/videos"
    return "https://www.youtube.com" + path


def normalize_playlist_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    values = parse_qs(parsed.query).get("list", [])
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() not in ALLOWED_HOSTS
        or parsed.path != "/playlist"
        or len(values) != 1
        or not PLAYLIST_ID.fullmatch(values[0])
    ):
        raise LucarneError("The YouTube playlist URL is invalid.")
    return f"https://www.youtube.com/playlist?list={values[0]}"


class YouTubeClient:
    def __init__(self, executable: str = "yt-dlp") -> None:
        self.executable = executable

    def run(self, arguments: list[str], timeout: int = 300, language: str | None = None) -> str:
        result = self._invoke(arguments, timeout, language)
        if not result.returncode:
            return result.stdout
        detail = self._detail(result)
        # One rule for every failure: its reason is read in English to tell a video to skip from a real error.
        reason = detail if language in (None, "en") else self._english_detail(arguments, timeout)
        if any(marker in reason.lower() for marker in UNAVAILABLE_MARKERS):
            raise VideoUnavailableError(detail, reason)
        raise YtDlpError(detail, reason or detail)

    def _invoke(self, arguments: list[str], timeout: int, language: str | None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.setdefault("LANG", "C.UTF-8")
        try:
            return subprocess.run(
                [
                    self.executable,
                    "--ignore-config",
                    "--no-cache-dir",
                    "--js-runtimes",
                    "deno",
                    *self._language_arguments(language),
                    *arguments,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise LucarneError("yt-dlp exceeded the allowed time.") from error

    @staticmethod
    def _detail(result: subprocess.CompletedProcess[str]) -> str:
        return (result.stderr or result.stdout or "Unknown yt-dlp error").strip()[-4000:]

    def _english_detail(self, arguments: list[str], timeout: int) -> str:
        """Ask again in English why the request failed; an empty text means the reason could not be read."""
        try:
            result = self._invoke(arguments, timeout, "en")
        except LucarneError:
            return ""
        return self._detail(result) if result.returncode else ""

    @staticmethod
    def _language_arguments(language: str | None) -> list[str]:
        """Ask YouTube for metadata in the given language; anything unexpected is ignored."""
        if language and METADATA_LANGUAGE.fullmatch(language):
            return ["--extractor-args", f"youtube:lang={language}"]
        return []

    def inspect_video(self, value: str, language: str = "en") -> dict[str, Any]:
        url = normalize_video_url(value)
        try:
            output = self.run(["--no-warnings", "--no-playlist", "--dump-single-json", url], 180, language)
        except VideoUnavailableError as error:
            if is_temporary(error.reason):
                error.release_timestamp = self._release_timestamp(url)
            raise
        try:
            data = json.loads(output)
        except json.JSONDecodeError as error:
            raise LucarneError("yt-dlp returned invalid metadata.") from error
        if not isinstance(data, dict) or not data.get("id"):
            raise LucarneError("The video does not expose usable metadata.")
        return data

    def _release_timestamp(self, url: str) -> int | None:
        """The exact start of a premiere or a live event: asked without failing on the missing formats, YouTube
        gives it in the metadata. Without it, the delay of the message is used."""
        try:
            output = self.run(
                ["--no-warnings", "--no-playlist", "--ignore-no-formats-error", "--dump-single-json", url], 180, "en"
            )
            data = json.loads(output)
        except (LucarneError, json.JSONDecodeError):
            return None
        stamp = data.get("release_timestamp") if isinstance(data, dict) else None
        return int(stamp) if data.get("live_status") == "is_upcoming" and isinstance(stamp, int | float) else None

    def discover(
        self, value: str, source_type: str, start: int, count: int, language: str = "en"
    ) -> dict[str, Any]:
        if not 1 <= count <= 50 or start < 1:
            raise LucarneError("Invalid catalogue range.")
        url = normalize_channel_url(value) if source_type == "channel" else normalize_playlist_url(value)
        end = start + count
        output = self.run(
            [
                "--no-warnings",
                "--ignore-errors",
                "--flat-playlist",
                "--playlist-items",
                f"{start}:{end}",
                "--dump-single-json",
                url,
            ],
            language=language,
        )
        try:
            data = json.loads(output)
        except json.JSONDecodeError as error:
            raise LucarneError("yt-dlp returned an invalid catalogue.") from error
        raw_entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(raw_entries, list):
            raise LucarneError("The source does not expose a usable catalogue.")
        entries = []
        for index, entry in enumerate(raw_entries[:count]):
            if not isinstance(entry, dict) or not VIDEO_ID.fullmatch(str(entry.get("id", ""))):
                continue
            timestamp = entry.get("timestamp") or entry.get("release_timestamp") or 0
            # `rank` is the place of the entry in the source, as YouTube lists it.
            entries.append({"id": str(entry["id"]), "timestamp": int(timestamp or 0), "rank": start + index})
        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "channel": data.get("channel"),
            "uploader": data.get("uploader"),
            "entries": entries,
            "has_more": len(raw_entries) > count,
            "next_offset": start - 1 + len(entries),
            "source_url": url,
            "image_url": self._image_url(data, source_type == "channel"),
        }

    def inspect_batch(
        self, video_ids: list[str], language: str = "en"
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Read the metadata of videos. A video that cannot be read never stops the others: it is described in
        the failures (see `classify_failure`) and the batch goes on."""
        if len(video_ids) > 50:
            raise LucarneError("A batch cannot contain more than 50 videos.")
        entries: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for index, video_id in enumerate(video_ids):
            if not VIDEO_ID.fullmatch(video_id):
                continue
            try:
                entries.append(self.inspect_video(f"https://www.youtube.com/watch?v={video_id}", language))
            except LucarneError as error:
                failures.append(classify_failure(video_id, error))
            if index + 1 < len(video_ids):
                time.sleep(random.uniform(2, 6))
        return entries, failures

    def download(
        self,
        url: str,
        destination: Path,
        mode: str,
        quality: str,
        audio_quality: str,
    ) -> Path:
        url = normalize_video_url(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        template = str(destination.with_suffix(".%(ext)s"))
        if mode == "audio":
            arguments = [
                "--format",
                "bestaudio/best",
                "--extract-audio",
                "--audio-format",
                "m4a",
                "--audio-quality",
                f"{audio_quality}K",
            ]
            expected_suffix = ".m4a"
        else:
            arguments = ["--format", quality_format(quality, audio_quality), "--merge-output-format", "mp4"]
            expected_suffix = ".mp4"
        output = self.run(
            [
                "--no-playlist",
                "--no-warnings",
                "--print",
                "after_move:filepath",
                "--output",
                template,
                *arguments,
                url,
            ],
            3600,
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        produced = Path(lines[-1]).resolve() if lines else destination.with_suffix(expected_suffix)
        if not produced.is_file() or produced.parent != destination.parent.resolve():
            raise LucarneError("yt-dlp did not produce the expected media file.")
        final_path = destination.with_suffix(expected_suffix)
        if produced != final_path:
            produced.replace(final_path)
        return final_path

    @staticmethod
    def _image_url(data: dict[str, Any], avatar_only: bool) -> str | None:
        candidates: list[tuple[int, str]] = []
        for item in data.get("thumbnails") or []:
            if not isinstance(item, dict) or not str(item.get("url", "")).startswith("https://"):
                continue
            identifier = str(item.get("id", "")).lower()
            if avatar_only and "avatar" not in identifier:
                continue
            area = int(item.get("width") or 0) * int(item.get("height") or 0)
            candidates.append((area, str(item["url"])))
        return max(candidates, default=(0, None))[1]
