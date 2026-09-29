"""Immediate playback downloads and retained media management."""

from __future__ import annotations

import mimetypes
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .assets import owner_key
from .config import Settings
from .database import Database
from .errors import ConflictError, NotFoundError, VideoUnavailableError
from .repository import Repository, now
from .youtube import YouTubeClient


class MediaService:
    def __init__(self, config: Settings, database: Database, repository: Repository, youtube: YouTubeClient) -> None:
        self.config = config
        self.db = database
        self.repository = repository
        self.youtube = youtube
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="lucarne-playback")

    def recover_interrupted(self) -> int:
        rows = self.db.all("SELECT id FROM downloads WHERE status IN ('queued','downloading')")
        for row in rows:
            for file in self.config.downloads.glob(f"{row['id']}.*"):
                file.unlink(missing_ok=True)
        if rows:
            with self.db.write() as connection:
                connection.execute(
                    """UPDATE downloads SET status='error',error='The application restarted during the download.',
                       updated_at=? WHERE status IN ('queued','downloading')""",
                    (now(),),
                )
        return len(rows)

    def stop(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def playback_settings(self, user_id: str, video: dict[str, Any], playlist_id: int | None = None) -> dict[str, str]:
        personal = self.repository.personal_settings(user_id)
        inherited: dict[str, Any] = {}
        if playlist_id is not None:
            try:
                inherited = self.repository.playlist(user_id, playlist_id)
            except NotFoundError:
                inherited = {}
        if not inherited and video.get("channel_id"):
            try:
                inherited = self.repository.channel(user_id, int(video["channel_id"]))
            except NotFoundError:
                inherited = {}
        return {
            "mode": str(video.get("mode") or inherited.get("mode") or personal["default_mode"]),
            "quality": str(video.get("quality") or inherited.get("quality") or personal["default_quality"]),
            "audio_quality": str(
                video.get("audio_quality") or inherited.get("audio_quality") or personal["default_audio_quality"]
            ),
        }

    def create_download(self, user_id: str, video_id: int, playlist_id: int | None = None) -> dict[str, Any]:
        video = self.repository.video(user_id, video_id)
        playback = self.playback_settings(user_id, video, playlist_id)
        existing = self.cached_download(user_id, video_id, playback)
        if existing:
            with self.db.write() as connection:
                connection.execute(
                    "UPDATE downloads SET accessed_at=?,updated_at=? WHERE id=?", (now(), now(), existing["id"])
                )
            if video.get("retained") and not existing.get("retained"):
                self.retain(user_id, video_id, True, str(existing["id"]))
                existing = self.cached_download(user_id, video_id, playback) or existing
            return self.download(user_id, str(existing["id"]))
        active_match = self.db.one(
            """SELECT * FROM downloads WHERE user_id=? AND video_id=? AND mode=? AND quality=? AND audio_quality=?
               AND status IN ('queued','downloading') ORDER BY created_at DESC LIMIT 1""",
            (user_id, video_id, playback["mode"], playback["quality"], playback["audio_quality"]),
        )
        if active_match:
            return active_match
        if video.get("availability") != "available":
            raise ConflictError(str(video.get("unavailable_reason") or "This video is no longer available on YouTube."))
        active = self.db.one(
            "SELECT COUNT(*) AS count FROM downloads WHERE user_id=? AND status IN ('queued','downloading')", (user_id,)
        )
        if int((active or {}).get("count", 0)) >= 4:
            raise ConflictError("Too many media downloads are already running.")
        download_id = uuid.uuid4().hex
        timestamp = now()
        with self.db.write() as connection:
            connection.execute(
                """INSERT INTO downloads(id,user_id,video_id,mode,quality,audio_quality,status,created_at,accessed_at,updated_at)
                   VALUES (?,?,?,?,?,?,'queued',?,?,?)""",
                (
                    download_id,
                    user_id,
                    video_id,
                    playback["mode"],
                    playback["quality"],
                    playback["audio_quality"],
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
        self.executor.submit(self._download, download_id, video)
        return self.download(user_id, download_id)

    def cached_download(
        self, user_id: str, video_id: int, playback: dict[str, str] | None = None
    ) -> dict[str, Any] | None:
        playback = playback or self.playback_settings(user_id, self.repository.video(user_id, video_id))
        retained = self.db.one(
            """SELECT * FROM downloads WHERE user_id=? AND video_id=? AND retained=1 AND status='ready'
               ORDER BY updated_at DESC LIMIT 1""",
            (user_id, video_id),
        )
        if retained and self.path_for(retained).is_file():
            return retained
        existing = self.db.one(
            """SELECT * FROM downloads WHERE user_id=? AND video_id=? AND mode=? AND quality=? AND audio_quality=?
               AND status='ready' ORDER BY retained DESC,updated_at DESC LIMIT 1""",
            (user_id, video_id, playback["mode"], playback["quality"], playback["audio_quality"]),
        )
        if existing and self.path_for(existing).is_file():
            return existing
        return None

    def _download(self, download_id: str, video: dict[str, Any]) -> None:
        row = self.db.one("SELECT * FROM downloads WHERE id=?", (download_id,))
        if not row:
            return
        with self.db.write() as connection:
            connection.execute(
                "UPDATE downloads SET status='downloading',updated_at=? WHERE id=?", (now(), download_id)
            )
        try:
            destination = self.config.downloads / download_id
            path = self.youtube.download(
                str(video["webpage_url"]), destination, str(row["mode"]), str(row["quality"]), str(row["audio_quality"])
            )
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            with self.db.write() as connection:
                connection.execute(
                    """UPDATE downloads SET status='ready',file_name=?,mime_type=?,size=?,updated_at=? WHERE id=?""",
                    (path.name, mime_type, path.stat().st_size, now(), download_id),
                )
            refreshed = self.repository.video(str(row["user_id"]), int(row["video_id"]))
            if refreshed.get("retained"):
                self.retain(str(row["user_id"]), int(row["video_id"]), True, download_id)
        except VideoUnavailableError as error:
            for file in self.config.downloads.glob(f"{download_id}.*"):
                file.unlink(missing_ok=True)
            with self.db.write() as connection:
                connection.execute(
                    "UPDATE downloads SET status='error',error=?,updated_at=? WHERE id=?",
                    (str(error)[-4000:], now(), download_id),
                )
                connection.execute(
                    """UPDATE videos SET availability='unavailable',unavailable_reason=?,availability_checked_at=?,updated_at=?
                       WHERE id=? AND user_id=?""",
                    (
                        "This video is private, deleted, or temporarily unavailable on YouTube.",
                        now(),
                        now(),
                        row["video_id"],
                        row["user_id"],
                    ),
                )
        except Exception as error:
            for file in self.config.downloads.glob(f"{download_id}.*"):
                file.unlink(missing_ok=True)
            with self.db.write() as connection:
                connection.execute(
                    "UPDATE downloads SET status='error',error=?,updated_at=? WHERE id=?",
                    (str(error)[-4000:], now(), download_id),
                )

    def download(self, user_id: str, download_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM downloads WHERE id=? AND user_id=?", (download_id, user_id))
        if not row:
            raise NotFoundError("Download not found.")
        return row

    def path_for(self, download: dict[str, Any]) -> Path:
        base = self.config.library if download.get("retained") else self.config.downloads
        return base / str(download.get("file_name") or "")

    def retain(self, user_id: str, video_id: int, retained: bool, download_id: str | None = None) -> dict[str, Any]:
        self.repository.video(user_id, video_id)
        if retained:
            if download_id is None:
                with self.db.write() as connection:
                    connection.execute("UPDATE videos SET retained=1,updated_at=? WHERE id=?", (now(), video_id))
                return self.repository.video(user_id, video_id)
            row = self.db.one(
                """SELECT * FROM downloads WHERE id=? AND user_id=? AND video_id=? AND status='ready' AND retained=0""",
                (download_id, user_id, video_id),
            )
            if not row or not self.path_for(row).is_file():
                raise NotFoundError("Download not found.")
            source = self.path_for(row)
            media_id = uuid.uuid4().hex
            destination = self.config.library / f"{media_id}{source.suffix}"
            if shutil.disk_usage(self.config.library).free < source.stat().st_size + 512 * 1024 * 1024:
                raise ConflictError("Not enough free space to retain this media.")
            shutil.copy2(source, destination)
            retained_download_id = uuid.uuid4().hex
            timestamp = now()
            previous = self.db.all(
                "SELECT * FROM downloads WHERE user_id=? AND video_id=? AND retained=1", (user_id, video_id)
            )
            with self.db.write() as connection:
                connection.execute(
                    """INSERT INTO downloads(
                         id,user_id,video_id,mode,quality,audio_quality,status,file_name,media_id,mime_type,size,
                         retained,created_at,accessed_at,updated_at
                       ) VALUES (?,?,?,?,?,?,'ready',?,?,?,?,1,?,?,?)""",
                    (
                        retained_download_id,
                        user_id,
                        video_id,
                        row["mode"],
                        row["quality"],
                        row["audio_quality"],
                        destination.name,
                        media_id,
                        row["mime_type"],
                        destination.stat().st_size,
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
                connection.execute(
                    "DELETE FROM downloads WHERE user_id=? AND video_id=? AND retained=1 AND id<>?",
                    (user_id, video_id, retained_download_id),
                )
                connection.execute("UPDATE videos SET retained=1,updated_at=? WHERE id=?", (timestamp, video_id))
            for previous_row in previous:
                self.path_for(previous_row).unlink(missing_ok=True)
        else:
            rows = self.db.all(
                "SELECT * FROM downloads WHERE user_id=? AND video_id=? AND retained=1", (user_id, video_id)
            )
            for row in rows:
                self.path_for(row).unlink(missing_ok=True)
            with self.db.write() as connection:
                connection.execute(
                    "DELETE FROM downloads WHERE user_id=? AND video_id=? AND retained=1", (user_id, video_id)
                )
                connection.execute("UPDATE videos SET retained=0,updated_at=? WHERE id=?", (now(), video_id))
        return self.repository.video(user_id, video_id)

    def cleanup(self) -> None:
        retention = int(self.repository.instance_settings()["temporary_retention_days"])
        threshold = now() - retention * 86400
        rows = self.db.all(
            "SELECT * FROM downloads WHERE retained=0 AND status NOT IN ('queued','downloading') AND accessed_at<?",
            (threshold,),
        )
        for row in rows:
            self.path_for(row).unlink(missing_ok=True)
        if rows:
            ids = [row["id"] for row in rows]
            with self.db.write() as connection:
                connection.executemany("DELETE FROM downloads WHERE id=?", [(value,) for value in ids])

    def delete_video_files(self, user_id: str, video_id: int) -> None:
        for row in self.db.all("SELECT * FROM downloads WHERE user_id=? AND video_id=?", (user_id, video_id)):
            self.path_for(row).unlink(missing_ok=True)
        for file in self.config.thumbnails.glob(f"{owner_key(user_id, video_id)}-*"):
            file.unlink(missing_ok=True)
