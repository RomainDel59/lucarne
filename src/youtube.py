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

from .errors import LucarneError, VideoUnavailableError

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,32}$")
PLAYLIST_ID = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
CHANNEL_PATH = re.compile(r"^/(?:@[^/]+|channel/[A-Za-z0-9_-]+|c/[^/]+|user/[^/]+)(?:/videos)?$")
ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
METADATA_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Z]{2})?")
UNAVAILABLE_MARKERS = (
    "video unavailable",
    "private video",
    "this video is unavailable",
    "has been removed",
    "members-only content",
    "join this channel",
    "join this channel to get access",
    "cette vidéo n'est pas disponible",
    "cette vidéo n’est pas disponible",
    "vidéo privée",
    "cette vidéo est privée",
    "a été supprimée",
    "réservé aux membres",
    "réservés aux membres",
    "contenu réservé aux membres",
    "contenus réservés aux membres",
)


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
        environment = os.environ.copy()
        environment.setdefault("LANG", "C.UTF-8")
        try:
            result = subprocess.run(
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
        if result.returncode:
            detail = (result.stderr or result.stdout or "Unknown yt-dlp error").strip()[-4000:]
            if any(marker in detail.lower() for marker in UNAVAILABLE_MARKERS):
                raise VideoUnavailableError(detail)
            raise LucarneError(detail)
        return result.stdout

    @staticmethod
    def _language_arguments(language: str | None) -> list[str]:
        """Ask YouTube for metadata in the given language; anything unexpected is ignored."""
        if language and METADATA_LANGUAGE.fullmatch(language):
            return ["--extractor-args", f"youtube:lang={language}"]
        return []

    def inspect_video(self, value: str, language: str = "en") -> dict[str, Any]:
        url = normalize_video_url(value)
        output = self.run(["--no-warnings", "--no-playlist", "--dump-single-json", url], 180, language)
        try:
            data = json.loads(output)
        except json.JSONDecodeError as error:
            raise LucarneError("yt-dlp returned invalid metadata.") from error
        if not isinstance(data, dict) or not data.get("id"):
            raise LucarneError("The video does not expose usable metadata.")
        return data

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
        for entry in raw_entries[:count]:
            if not isinstance(entry, dict) or not VIDEO_ID.fullmatch(str(entry.get("id", ""))):
                continue
            timestamp = entry.get("timestamp") or entry.get("release_timestamp") or 0
            entries.append({"id": str(entry["id"]), "timestamp": int(timestamp or 0)})
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
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if len(video_ids) > 50:
            raise LucarneError("A batch cannot contain more than 50 videos.")
        entries: list[dict[str, Any]] = []
        unavailable: list[str] = []
        for index, video_id in enumerate(video_ids):
            if not VIDEO_ID.fullmatch(video_id):
                continue
            try:
                entries.append(self.inspect_video(f"https://www.youtube.com/watch?v={video_id}", language))
            except VideoUnavailableError:
                unavailable.append(video_id)
            if index + 1 < len(video_ids):
                time.sleep(random.uniform(2, 6))
        return entries, unavailable

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
