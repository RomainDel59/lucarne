"""Domain repository built on top of SQLite."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit

from .database import Database, placeholders
from .errors import ConflictError, NotFoundError
from .localization import SUPPORTED_LANGUAGES


def now() -> int:
    return int(time.time())


def normalize_name(value: str) -> tuple[str, str]:
    name = " ".join(value.split()).strip()
    if not name or len(name) > 100:
        raise ValueError("A name between 1 and 100 characters is required.")
    return name, name.casefold()


def published_timestamp(metadata: dict[str, Any]) -> int:
    """Resolve the publication date using the same fallbacks exposed by yt-dlp."""
    for field in ("timestamp", "release_timestamp"):
        value = metadata.get(field)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    upload_date = str(metadata.get("upload_date") or "")
    if len(upload_date) == 8 and upload_date.isdigit():
        try:
            return int(datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=UTC, hour=12).timestamp())
        except ValueError:
            pass
    return 0


def pending_channel_title(source_url: str) -> str:
    for part in urlsplit(source_url).path.split("/"):
        if part.startswith("@") and len(part) > 1:
            return part[:255]
    return "Pending channel"


class Repository:
    def __init__(self, database: Database) -> None:
        self.db = database

    def personal_settings(self, user_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        if row:
            return row
        timestamp = now()
        with self.db.write() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO user_settings(user_id, created_at, updated_at) VALUES (?, ?, ?)",
                (user_id, timestamp, timestamp),
            )
        return self.db.one("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)) or {}

    def update_personal_settings(self, user_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self.personal_settings(user_id)
        mode = str(values.get("default_mode", "video"))
        quality = str(values.get("default_quality", "720"))
        audio = str(values.get("default_audio_quality", "128"))
        history_limit = int(values.get("history_limit", 0))
        self._validate_playback(mode, quality, audio)
        if not 0 <= history_limit <= 100000:
            raise ValueError("The history limit must be between 0 and 100000.")
        with self.db.write() as connection:
            connection.execute(
                """UPDATE user_settings
                   SET default_mode = ?, default_quality = ?, default_audio_quality = ?,
                       history_limit = ?, updated_at = ? WHERE user_id = ?""",
                (mode, quality, audio, history_limit, now(), user_id),
            )
        return self.personal_settings(user_id)

    def instance_settings(self) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM instance_settings WHERE singleton = 1")
        if row:
            return row
        with self.db.write() as connection:
            connection.execute("INSERT OR IGNORE INTO instance_settings(singleton, updated_at) VALUES (1, ?)", (now(),))
        return self.db.one("SELECT * FROM instance_settings WHERE singleton = 1") or {}

    def metadata_language(self) -> str:
        """Return the language YouTube titles and descriptions are fetched in; English until one is set."""
        return str(self.instance_settings()["metadata_language"] or "en")

    def has_metadata_language(self) -> bool:
        return self.instance_settings()["metadata_language"] is not None

    def set_metadata_language_if_unset(self, language: str) -> None:
        """Initialize the metadata language once, never overriding a value an administrator may have chosen."""
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError("The YouTube metadata language is not supported.")
        self.instance_settings()
        with self.db.write() as connection:
            connection.execute(
                "UPDATE instance_settings SET metadata_language = ?, updated_at = ? "
                "WHERE singleton = 1 AND metadata_language IS NULL",
                (language, now()),
            )

    def update_instance_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        current = self.instance_settings()
        language = values.get("metadata_language") or current["metadata_language"]
        if language is not None and language not in SUPPORTED_LANGUAGES:
            raise ValueError("The YouTube metadata language is not supported.")
        batch_size = int(values.get("batch_size", 10))
        lot_wait = int(values.get("lot_wait_seconds", 300))
        duration = int(values.get("campaign_duration_seconds", 7200))
        retention = int(values.get("temporary_retention_days", 7))
        if not 1 <= batch_size <= 50:
            raise ValueError("The batch size must be between 1 and 50.")
        if lot_wait not in {60, 120, 300, 600, 900, 1800, 3600}:
            raise ValueError("The delay between batches is invalid.")
        if duration not in {1800, 3600, 7200, 14400, 28800, 43200}:
            raise ValueError("The campaign duration is invalid.")
        if not 1 <= retention <= 365:
            raise ValueError("Temporary media retention must be between 1 and 365 days.")
        with self.db.write() as connection:
            connection.execute(
                """UPDATE instance_settings SET batch_size = ?, lot_wait_seconds = ?,
                   campaign_duration_seconds = ?, temporary_retention_days = ?, metadata_language = ?,
                   updated_at = ? WHERE singleton = 1""",
                (batch_size, lot_wait, duration, retention, language, now()),
            )
        return self.instance_settings()

    def apply_instance_settings(self) -> None:
        settings = self.instance_settings()
        timestamp = now()
        campaigns = self.db.all("SELECT id,user_id,started_at FROM campaigns WHERE status='running'")
        with self.db.write() as connection:
            for campaign in campaigns:
                wait = self.randomized_wait(int(settings["lot_wait_seconds"]))
                next_lot_at = timestamp + wait
                connection.execute(
                    "UPDATE campaigns SET deadline_at=?,next_lot_at=?,updated_at=? WHERE id=?",
                    (
                        int(campaign["started_at"]) + int(settings["campaign_duration_seconds"]),
                        next_lot_at,
                        timestamp,
                        campaign["id"],
                    ),
                )
                connection.execute(
                    "UPDATE agent_jobs SET available_at=? WHERE user_id=? AND status='queued'",
                    (next_lot_at, campaign["user_id"]),
                )

    @staticmethod
    def randomized_wait(base: int) -> int:
        import random

        return random.randint(max(1, base // 2), max(1, (base * 3 + 1) // 2))

    def channels(
        self, user_id: str, catalog_id: int | None = None, uncategorized: bool = False
    ) -> list[dict[str, Any]]:
        condition = "c.user_id = ? AND c.deleting = 0 AND c.subscribed = 1"
        parameters: list[Any] = [user_id]
        if catalog_id is not None:
            condition += (
                " AND EXISTS (SELECT 1 FROM channel_catalog_memberships m WHERE m.channel_id=c.id AND m.catalog_id=?)"
            )
            parameters.append(catalog_id)
        elif uncategorized:
            condition += " AND NOT EXISTS (SELECT 1 FROM channel_catalog_memberships m WHERE m.channel_id=c.id)"
        return self.db.all(
            f"""SELECT c.*, COUNT(v.id) AS video_count, MAX(v.published_at) AS latest_published_at
                FROM channels c LEFT JOIN videos v ON v.channel_id=c.id AND v.user_id=c.user_id
                WHERE {condition} GROUP BY c.id ORDER BY c.title COLLATE NOCASE, c.id""",
            tuple(parameters),
        )

    def channel(self, user_id: str, channel_id: int) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM channels WHERE id = ? AND user_id = ?", (channel_id, user_id))
        if not row:
            raise NotFoundError("Channel not found.")
        return row

    def channel_by_source_url(self, user_id: str, source_url: str) -> dict[str, Any] | None:
        return self.db.one("SELECT * FROM channels WHERE user_id=? AND source_url=?", (user_id, source_url))

    def create_channel(self, user_id: str, source_url: str) -> dict[str, Any]:
        timestamp = now()
        existing = self.db.one("SELECT * FROM channels WHERE user_id=? AND source_url=?", (user_id, source_url))
        if existing:
            if not existing["subscribed"] or existing["deleting"]:
                with self.db.write() as connection:
                    connection.execute(
                        """UPDATE channels SET subscribed=1,deleting=0,
                           sync_status=CASE WHEN external_id LIKE 'pending_%' THEN 'initializing' ELSE sync_status END,
                           sync_error=CASE WHEN external_id LIKE 'pending_%' THEN NULL ELSE sync_error END,updated_at=?
                           WHERE id=?""",
                        (timestamp, existing["id"]),
                    )
            return self.channel(user_id, int(existing["id"]))
        pending_id = "pending_" + hashlib.sha256(source_url.encode()).hexdigest()[:56]
        try:
            with self.db.write() as connection:
                cursor = connection.execute(
                    """INSERT INTO channels(user_id,source_url,external_id,title,sync_status,created_at,updated_at)
                       VALUES (?,?,?,?,'initializing',?,?)""",
                    (user_id, source_url, pending_id, pending_channel_title(source_url), timestamp, timestamp),
                )
                channel_id = int(cursor.lastrowid)
        except Exception as error:
            existing = self.db.one("SELECT * FROM channels WHERE user_id=? AND source_url=?", (user_id, source_url))
            if existing:
                return existing
            raise error
        return self.channel(user_id, channel_id)

    def update_channel(self, user_id: str, channel_id: int, values: dict[str, Any]) -> dict[str, Any]:
        self.channel(user_id, channel_id)
        mode, quality, audio, history = self._nullable_playback(values)
        with self.db.write() as connection:
            connection.execute(
                """UPDATE channels SET mode=?, quality=?, audio_quality=?, history_limit=?, updated_at=?
                   WHERE id=? AND user_id=?""",
                (mode, quality, audio, history, now(), channel_id, user_id),
            )
        return self.channel(user_id, channel_id)

    def mark_channel_deleting(self, user_id: str, channel_id: int) -> dict[str, Any]:
        row = self.channel(user_id, channel_id)
        with self.db.write() as connection:
            connection.execute("UPDATE channels SET deleting=1, updated_at=? WHERE id=?", (now(), channel_id))
            connection.execute("DELETE FROM channel_catalog_memberships WHERE channel_id=?", (channel_id,))
        return row

    def unsubscribe_channel(self, user_id: str, channel_id: int) -> None:
        self.channel(user_id, channel_id)
        with self.db.write() as connection:
            connection.execute(
                "UPDATE channels SET subscribed=0,deleting=0,sync_status='idle',sync_error=NULL,updated_at=? WHERE id=? AND user_id=?",
                (now(), channel_id, user_id),
            )

    def playlists(self, user_id: str) -> list[dict[str, Any]]:
        return self.db.all(
            """SELECT p.*, COUNT(pv.video_id) AS video_count, MAX(v.published_at) AS latest_published_at,
                      (SELECT v2.thumbnail_file FROM playlist_videos pv2 JOIN videos v2 ON v2.id=pv2.video_id
                       WHERE pv2.playlist_id=p.id ORDER BY pv2.position, pv2.added_at, pv2.video_id LIMIT 1) AS cover_file
               FROM playlists p LEFT JOIN playlist_videos pv ON pv.playlist_id=p.id
               LEFT JOIN videos v ON v.id=pv.video_id
               WHERE p.user_id=? AND p.deleting=0 GROUP BY p.id ORDER BY p.title COLLATE NOCASE, p.id""",
            (user_id,),
        )

    def playlist(self, user_id: str, playlist_id: int) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM playlists WHERE id=? AND user_id=?", (playlist_id, user_id))
        if not row:
            raise NotFoundError("Playlist not found.")
        return row

    def create_playlist(self, user_id: str, title: str, source_url: str | None = None) -> dict[str, Any]:
        title = title.strip()
        if not title:
            raise ValueError("A playlist title is required.")
        title = title[:255]
        if source_url:
            existing = self.db.one("SELECT * FROM playlists WHERE user_id=? AND source_url=?", (user_id, source_url))
            if existing:
                if existing["deleting"]:
                    raise ConflictError("This playlist is being deleted.")
                return existing
        pending_id = "pending_" + hashlib.sha256(source_url.encode()).hexdigest()[:56] if source_url else None
        timestamp = now()
        with self.db.write() as connection:
            cursor = connection.execute(
                """INSERT INTO playlists(user_id,title,source_url,external_id,kind,sync_status,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    user_id,
                    title,
                    source_url,
                    pending_id,
                    "youtube" if source_url else "personal",
                    "initializing" if source_url else "idle",
                    timestamp,
                    timestamp,
                ),
            )
            playlist_id = int(cursor.lastrowid)
        return self.playlist(user_id, playlist_id)

    def update_playlist(self, user_id: str, playlist_id: int, values: dict[str, Any]) -> dict[str, Any]:
        current = self.playlist(user_id, playlist_id)
        title = str(values.get("title") or current["title"]).strip()
        if not title:
            raise ValueError("A playlist title is required.")
        if current["kind"] == "youtube":
            title = str(current["title"])
        title = title[:255]
        mode, quality, audio, history = self._nullable_playback(values)
        with self.db.write() as connection:
            connection.execute(
                """UPDATE playlists SET title=?,mode=?,quality=?,audio_quality=?,history_limit=?,updated_at=?
                   WHERE id=? AND user_id=?""",
                (title, mode, quality, audio, history, now(), playlist_id, user_id),
            )
        return self.playlist(user_id, playlist_id)

    def mark_playlist_deleting(self, user_id: str, playlist_id: int) -> dict[str, Any]:
        row = self.playlist(user_id, playlist_id)
        with self.db.write() as connection:
            connection.execute("UPDATE playlists SET deleting=1,updated_at=? WHERE id=?", (now(), playlist_id))
        return row

    def videos(
        self,
        user_id: str,
        page: int = 1,
        channel_id: int | None = None,
        playlist_id: int | None = None,
        catalog_id: int | None = None,
        uncategorized: bool = False,
        search: str = "",
        pending_count: int = 0,
        page_size: int = 10,
    ) -> dict[str, Any]:
        page = max(1, page)
        conditions = ["v.user_id=?", "v.deleting=0"]
        parameters: list[Any] = [user_id]
        joins = ""
        if channel_id is not None:
            conditions.append("v.channel_id=?")
            parameters.append(channel_id)
        if playlist_id is not None:
            joins += " JOIN playlist_videos pv ON pv.video_id=v.id"
            conditions.append("pv.playlist_id=?")
            parameters.append(playlist_id)
        if catalog_id is not None:
            joins += " JOIN channel_catalog_memberships cm ON cm.channel_id=v.channel_id"
            conditions.append("cm.catalog_id=?")
            parameters.append(catalog_id)
        elif uncategorized:
            conditions.append(
                "(v.channel_id IS NULL OR NOT EXISTS (SELECT 1 FROM channel_catalog_memberships cm WHERE cm.channel_id=v.channel_id))"
            )
        if search.strip():
            conditions.append("(v.title LIKE ? ESCAPE '\\' OR v.channel_name LIKE ? ESCAPE '\\')")
            term = "%" + search.strip().replace("%", "\\%").replace("_", "\\_") + "%"
            parameters.extend([term, term])
        where = " AND ".join(conditions)
        total = self.db.one(
            f"SELECT COUNT(DISTINCT v.id) AS count FROM videos v{joins} WHERE {where}", tuple(parameters)
        )
        offset = (page - 1) * page_size
        pending_on_page = max(0, min(page_size, pending_count - offset))
        video_limit = page_size - pending_on_page
        video_offset = max(0, offset - pending_count)
        rows = (
            self.db.all(
                f"""SELECT DISTINCT v.*, h.position AS history_position, h.duration AS history_duration,
                           h.completed AS history_completed
                    FROM videos v{joins} LEFT JOIN histories h ON h.video_id=v.id AND h.user_id=v.user_id
                    WHERE {where} ORDER BY v.published_at DESC, v.id DESC LIMIT ? OFFSET ?""",
                tuple([*parameters, video_limit, video_offset]),
            )
            if video_limit
            else []
        )
        return {
            "items": rows,
            "page": page,
            "page_size": page_size,
            "total": int((total or {}).get("count", 0)) + pending_count,
        }

    def pending_video_jobs(self, user_id: str, playlist_id: int | None = None) -> list[dict[str, Any]]:
        rows = self.db.all(
            """SELECT * FROM agent_jobs WHERE user_id=? AND type='inspect_video'
               AND status IN ('queued','running','error') ORDER BY created_at DESC,id DESC""",
            (user_id,),
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload"] or "{}")
            job_playlist_id = int(payload.get("playlist_id") or 0)
            if playlist_id is not None and job_playlist_id != playlist_id:
                continue
            row["payload"] = payload
            result.append(row)
        return result

    def video(self, user_id: str, video_id: int) -> dict[str, Any]:
        row = self.db.one(
            """SELECT v.*,h.position AS history_position,h.duration AS history_duration,h.completed AS history_completed
               FROM videos v LEFT JOIN histories h ON h.video_id=v.id AND h.user_id=v.user_id
               WHERE v.id=? AND v.user_id=?""",
            (video_id, user_id),
        )
        if not row:
            raise NotFoundError("Video not found.")
        row["playlist_ids"] = [
            item["playlist_id"]
            for item in self.db.all("SELECT playlist_id FROM playlist_videos WHERE video_id=?", (video_id,))
        ]
        return row

    def video_by_youtube_id(self, user_id: str, youtube_id: str) -> dict[str, Any] | None:
        return self.db.one("SELECT * FROM videos WHERE user_id=? AND youtube_id=?", (user_id, youtube_id))

    def store_video(self, user_id: str, metadata: dict[str, Any], channel_id: int | None = None) -> dict[str, Any]:
        youtube_id = str(metadata.get("id", ""))
        if not youtube_id:
            raise ValueError("Video metadata does not contain an identifier.")
        timestamp = now()
        published = published_timestamp(metadata)
        title = str(metadata.get("title") or youtube_id)[:500]
        description = str(metadata.get("description") or "")
        channel_name = str(metadata.get("channel") or metadata.get("uploader") or "")[:255]
        external_id = str(metadata.get("channel_id") or metadata.get("uploader_id") or "")[:128]
        if channel_id is None and external_id:
            channel = self.db.one("SELECT * FROM channels WHERE user_id=? AND external_id=?", (user_id, external_id))
            if channel is None:
                source_url = f"https://www.youtube.com/channel/{quote(external_id, safe='-_')}/videos"
                with self.db.write() as connection:
                    cursor = connection.execute(
                        """INSERT INTO channels(user_id,source_url,external_id,title,subscribed,sync_status,created_at,updated_at)
                           VALUES (?,?,?,?,0,'idle',?,?)""",
                        (user_id, source_url, external_id, channel_name or "YouTube channel", timestamp, timestamp),
                    )
                    channel_id = int(cursor.lastrowid)
            else:
                channel_id = int(channel["id"])
        with self.db.write() as connection:
            connection.execute(
                """INSERT INTO videos(user_id,youtube_id,webpage_url,title,description,channel_id,channel_name,
                                      published_at,duration,availability,availability_checked_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,'available',?,?,?)
                   ON CONFLICT(user_id,youtube_id) DO UPDATE SET
                     title=excluded.title,description=excluded.description,
                     channel_id=COALESCE(excluded.channel_id,videos.channel_id),channel_name=excluded.channel_name,
                     published_at=excluded.published_at,duration=excluded.duration,availability='available',
                     unavailable_reason=NULL,availability_checked_at=excluded.updated_at,deleting=0,updated_at=excluded.updated_at""",
                (
                    user_id,
                    youtube_id,
                    str(metadata.get("webpage_url") or f"https://www.youtube.com/watch?v={youtube_id}"),
                    title,
                    description,
                    channel_id,
                    channel_name,
                    published,
                    int(metadata.get("duration") or 0),
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
        return self.video_by_youtube_id(user_id, youtube_id) or {}

    def update_video_settings(self, user_id: str, video_id: int, values: dict[str, Any]) -> dict[str, Any]:
        self.video(user_id, video_id)
        mode, quality, audio, _ = self._nullable_playback(values, allow_history=False)
        with self.db.write() as connection:
            connection.execute(
                "UPDATE videos SET mode=?,quality=?,audio_quality=?,updated_at=? WHERE id=? AND user_id=?",
                (mode, quality, audio, now(), video_id, user_id),
            )
        return self.video(user_id, video_id)

    def delete_video(self, user_id: str, video_id: int) -> None:
        self.video(user_id, video_id)
        with self.db.write() as connection:
            connection.execute("DELETE FROM videos WHERE id=? AND user_id=?", (video_id, user_id))

    def mark_video_deleting(self, user_id: str, video_id: int) -> dict[str, Any]:
        row = self.video(user_id, video_id)
        with self.db.write() as connection:
            connection.execute(
                "UPDATE videos SET deleting=1,updated_at=? WHERE id=? AND user_id=?", (now(), video_id, user_id)
            )
        return row

    def attach_video(self, user_id: str, playlist_id: int, video_id: int) -> None:
        self.playlist(user_id, playlist_id)
        self.video(user_id, video_id)
        with self.db.write() as connection:
            position = connection.execute(
                "SELECT COALESCE(MAX(position),-1)+1 AS position FROM playlist_videos WHERE playlist_id=?",
                (playlist_id,),
            ).fetchone()["position"]
            connection.execute(
                "INSERT OR IGNORE INTO playlist_videos(playlist_id,video_id,position,added_at) VALUES (?,?,?,?)",
                (playlist_id, video_id, position, now()),
            )

    def detach_video(self, user_id: str, playlist_id: int, video_id: int) -> None:
        self.playlist(user_id, playlist_id)
        with self.db.write() as connection:
            connection.execute(
                "DELETE FROM playlist_videos WHERE playlist_id=? AND video_id=?", (playlist_id, video_id)
            )

    def catalogs(self, user_id: str) -> list[dict[str, Any]]:
        return self.db.all(
            """SELECT c.*,COUNT(m.channel_id) AS channel_count FROM channel_catalogs c
               LEFT JOIN channel_catalog_memberships m ON m.catalog_id=c.id
               WHERE c.user_id=? GROUP BY c.id ORDER BY c.name COLLATE NOCASE,c.id""",
            (user_id,),
        )

    def catalog(self, user_id: str, catalog_id: int) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM channel_catalogs WHERE id=? AND user_id=?", (catalog_id, user_id))
        if not row:
            raise NotFoundError("Catalogue not found.")
        row["channel_ids"] = [
            item["channel_id"]
            for item in self.db.all(
                "SELECT channel_id FROM channel_catalog_memberships WHERE catalog_id=? ORDER BY channel_id",
                (catalog_id,),
            )
        ]
        return row

    def create_catalog(self, user_id: str, name: str) -> dict[str, Any]:
        name, normalized = normalize_name(name)
        timestamp = now()
        try:
            with self.db.write() as connection:
                cursor = connection.execute(
                    "INSERT INTO channel_catalogs(user_id,name,normalized_name,created_at,updated_at) VALUES (?,?,?,?,?)",
                    (user_id, name, normalized, timestamp, timestamp),
                )
                catalog_id = int(cursor.lastrowid)
        except Exception as error:
            raise ConflictError("A catalogue with this name already exists.") from error
        return self.catalog(user_id, catalog_id)

    def update_catalog(self, user_id: str, catalog_id: int, name: str) -> dict[str, Any]:
        self.catalog(user_id, catalog_id)
        name, normalized = normalize_name(name)
        try:
            with self.db.write() as connection:
                connection.execute(
                    "UPDATE channel_catalogs SET name=?,normalized_name=?,updated_at=? WHERE id=? AND user_id=?",
                    (name, normalized, now(), catalog_id, user_id),
                )
        except Exception as error:
            raise ConflictError("A catalogue with this name already exists.") from error
        return self.catalog(user_id, catalog_id)

    def replace_catalog_channels(self, user_id: str, catalog_id: int, channel_ids: list[int]) -> dict[str, Any]:
        self.catalog(user_id, catalog_id)
        channel_ids = sorted(set(int(value) for value in channel_ids))
        if channel_ids:
            found = self.db.all(
                f"SELECT id FROM channels WHERE user_id=? AND id IN ({placeholders(channel_ids)})",
                tuple([user_id, *channel_ids]),
            )
            if len(found) != len(channel_ids):
                raise ValueError("One or more channels do not belong to the active user.")
        with self.db.write() as connection:
            connection.execute("DELETE FROM channel_catalog_memberships WHERE catalog_id=?", (catalog_id,))
            connection.executemany(
                "INSERT INTO channel_catalog_memberships(catalog_id,channel_id) VALUES (?,?)",
                [(catalog_id, value) for value in channel_ids],
            )
        return self.catalog(user_id, catalog_id)

    def add_channel_to_catalog(self, user_id: str, catalog_id: int, channel_id: int) -> dict[str, Any]:
        """Add one channel to a catalogue, keeping its other memberships; adding it twice changes nothing."""
        self.catalog(user_id, catalog_id)
        if not self.db.one("SELECT id FROM channels WHERE id=? AND user_id=?", (channel_id, user_id)):
            raise NotFoundError("Channel not found.")
        with self.db.write() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO channel_catalog_memberships(catalog_id,channel_id) VALUES (?,?)",
                (catalog_id, channel_id),
            )
        return self.catalog(user_id, catalog_id)

    def remove_channel_from_catalog(self, user_id: str, catalog_id: int, channel_id: int) -> dict[str, Any]:
        """Remove one channel from a catalogue only; removing an absent channel changes nothing."""
        self.catalog(user_id, catalog_id)
        with self.db.write() as connection:
            connection.execute(
                "DELETE FROM channel_catalog_memberships WHERE catalog_id=? AND channel_id=?",
                (catalog_id, channel_id),
            )
        return self.catalog(user_id, catalog_id)

    def delete_catalog(self, user_id: str, catalog_id: int) -> None:
        self.catalog(user_id, catalog_id)
        with self.db.write() as connection:
            connection.execute("DELETE FROM channel_catalogs WHERE id=? AND user_id=?", (catalog_id, user_id))

    def history(self, user_id: str, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        page = max(1, page)
        total = self.db.one(
            """SELECT COUNT(*) AS count FROM histories h JOIN videos v ON v.id=h.video_id AND v.user_id=h.user_id
               WHERE h.user_id=? AND v.deleting=0""",
            (user_id,),
        )
        items = self.db.all(
            """SELECT v.*,h.position AS history_position,h.duration AS history_duration,h.completed AS history_completed,
                      h.updated_at AS history_updated_at
               FROM histories h JOIN videos v ON v.id=h.video_id AND v.user_id=h.user_id
               WHERE h.user_id=? AND v.deleting=0 ORDER BY h.updated_at DESC LIMIT ? OFFSET ?""",
            (user_id, page_size, (page - 1) * page_size),
        )
        return {"items": items, "page": page, "page_size": page_size, "total": int((total or {}).get("count", 0))}

    def save_history(self, user_id: str, video_id: int, position: float, duration: float | None) -> None:
        self.video(user_id, video_id)
        completed = bool(duration and position >= max(0, duration - 15))
        with self.db.write() as connection:
            connection.execute(
                """INSERT INTO histories(user_id,video_id,position,duration,completed,updated_at) VALUES (?,?,?,?,?,?)
                   ON CONFLICT(user_id,video_id) DO UPDATE SET position=excluded.position,duration=excluded.duration,
                   completed=excluded.completed,updated_at=excluded.updated_at""",
                (user_id, video_id, max(0, position), duration, int(completed), now()),
            )

    def clear_history(self, user_id: str, video_id: int | None = None) -> None:
        with self.db.write() as connection:
            if video_id is None:
                connection.execute("DELETE FROM histories WHERE user_id=?", (user_id,))
            else:
                connection.execute("DELETE FROM histories WHERE user_id=? AND video_id=?", (user_id, video_id))

    def enqueue(
        self,
        user_id: str,
        job_type: str,
        target_type: str | None,
        target_id: int | None,
        payload: dict[str, Any] | None = None,
        manual: bool = True,
    ) -> dict[str, Any]:
        campaign = self.ensure_campaign(user_id)
        encoded_payload = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        active = self.db.all(
            """SELECT * FROM agent_jobs WHERE user_id=? AND type=? AND status IN ('queued','running')
               AND target_type IS ? AND target_id IS ?""",
            (user_id, job_type, target_type, target_id),
        )
        for candidate in active:
            try:
                normalized = json.dumps(json.loads(candidate["payload"] or "{}"), ensure_ascii=False, sort_keys=True)
            except (TypeError, json.JSONDecodeError):
                continue
            if normalized == encoded_payload:
                return self.job(user_id, int(candidate["id"]))
        if manual:
            priority_row = self.db.one(
                "SELECT COALESCE(MAX(priority),0) AS value FROM agent_jobs WHERE user_id=? AND status='queued'",
                (user_id,),
            )
            priority = int((priority_row or {}).get("value", 0)) + 10
        else:
            priority_row = self.db.one(
                "SELECT COALESCE(MIN(priority),0) AS value FROM agent_jobs WHERE user_id=? AND status='queued'",
                (user_id,),
            )
            priority = int((priority_row or {}).get("value", 0)) - 10
        timestamp = now()
        with self.db.write() as connection:
            cursor = connection.execute(
                """INSERT INTO agent_jobs(user_id,campaign_id,type,target_type,target_id,payload,status,manual,priority,
                                          available_at,created_at)
                   VALUES (?,?,?,?,?,?,'queued',?,?,?,?)""",
                (
                    user_id,
                    campaign["id"],
                    job_type,
                    target_type,
                    target_id,
                    encoded_payload,
                    int(manual),
                    priority,
                    campaign["next_lot_at"],
                    timestamp,
                ),
            )
            job_id = int(cursor.lastrowid)
        return self.job(user_id, job_id)

    def ensure_campaign(self, user_id: str) -> dict[str, Any]:
        active = self.db.one(
            "SELECT * FROM campaigns WHERE user_id=? AND status='running' ORDER BY id DESC LIMIT 1", (user_id,)
        )
        if active:
            return active
        settings = self.instance_settings()
        timestamp = now()
        with self.db.write() as connection:
            cursor = connection.execute(
                """INSERT INTO campaigns(user_id,status,phase,started_at,deadline_at,next_lot_at,updated_at)
                   VALUES (?,'running','discover',?,?,?,?)""",
                (
                    user_id,
                    timestamp,
                    timestamp + int(settings["campaign_duration_seconds"]),
                    timestamp + self.randomized_wait(int(settings["lot_wait_seconds"])),
                    timestamp,
                ),
            )
            campaign_id = int(cursor.lastrowid)
        return self.db.one("SELECT * FROM campaigns WHERE id=?", (campaign_id,)) or {}

    def job(self, user_id: str, job_id: int) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM agent_jobs WHERE id=? AND user_id=?", (job_id, user_id))
        if not row:
            raise NotFoundError("Agent batch not found.")
        row["payload"] = json.loads(row["payload"] or "{}")
        return row

    def agent_status(self, user_id: str) -> dict[str, Any]:
        campaign = self.ensure_campaign(user_id)
        jobs = self.db.all(
            """SELECT * FROM agent_jobs WHERE user_id=? AND status IN ('running','queued','error')
               ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,
                        priority DESC,created_at,id LIMIT 500""",
            (user_id,),
        )
        for job in jobs:
            job["payload"] = json.loads(job["payload"] or "{}")
            job["presentation"] = self._present_job(user_id, job)
        return {
            "campaign": campaign,
            "jobs": jobs,
            "future_steps": self._future_steps(str(campaign.get("phase") or "discover")),
            "server_time": now(),
        }

    def _present_job(self, user_id: str, job: dict[str, Any]) -> dict[str, Any]:
        payload = job.get("payload") or {}
        job_type = str(job.get("type") or "")
        target_type = str(job.get("target_type") or "")
        target_id = int(job.get("target_id") or 0)
        if job_type == "discover":
            details = [
                self._source_label(user_id, str(source.get("type") or ""), int(source.get("id") or 0))
                for source in payload.get("sources", [])
            ]
            count = len(details)
            return {
                "title": "Check {count} source" if count == 1 else "Check {count} sources",
                "variables": {"count": count},
                "summary": "Channels and playlists to query",
                "details": details,
            }
        if job_type == "metadata":
            ids = [int(value) for value in payload.get("candidate_ids", [])]
            details = []
            if ids:
                rows = self.db.all(
                    f"SELECT * FROM candidates WHERE user_id=? AND id IN ({placeholders(ids)})",
                    (user_id, *ids),
                )
                details = [
                    f"{self._source_label(user_id, row['source_type'], int(row['source_id']))} · video {row['youtube_id']}"
                    for row in rows
                ]
            count = len(ids)
            return {
                "title": "Collect metadata for {count} video" if count == 1 else "Collect metadata for {count} videos",
                "variables": {"count": count},
                "summary": "Titles, dates, descriptions and thumbnails",
                "details": details,
            }
        if job_type == "history" and target_type and target_id:
            known = self._source_video_count(user_id, target_type, target_id)
            limit = self._source_history_limit(user_id, target_type, target_id)
            limit_label = "unlimited" if limit == 0 else f"limit {limit}"
            return {
                "title": "Collect up to {count} historical videos",
                "variables": {"count": self.instance_settings()["batch_size"]},
                "summary": self._source_label(user_id, target_type, target_id),
                "details": [f"{known} known videos · {limit_label}"],
            }
        label = self._target_label(user_id, target_type, target_id)
        url = str(payload.get("url") or "").strip()
        names = {
            "initialize_channel": "Add a subscription",
            "initialize_playlist": "Import a playlist",
            "sync_source": "Reactivate a subscription",
            "inspect_video": "Add a video",
            "delete_channel": "Delete a subscription",
            "delete_playlist": "Delete a playlist",
            "delete_video": "Delete a video",
        }
        details: list[str] = [url] if url else []
        if job_type in {"initialize_channel", "initialize_playlist"} and target_id:
            table = "channels" if job_type == "initialize_channel" else "playlists"
            source = self.db.one(f"SELECT source_url FROM {table} WHERE id=? AND user_id=?", (target_id, user_id))
            if source and source.get("source_url"):
                details = [str(source["source_url"])]
        if job_type in {"delete_channel", "delete_playlist"}:
            details = ["Also delete videos from Lucarne" if payload.get("delete_videos") else "Keep videos in Lucarne"]
        if job_type == "inspect_video" and payload.get("playlist_id"):
            label = self._source_label(user_id, "playlist", int(payload["playlist_id"]))
        return {"title": names.get(job_type, job_type), "summary": label, "details": details}

    def _source_label(self, user_id: str, source_type: str, source_id: int) -> str:
        table = "channels" if source_type == "channel" else "playlists" if source_type == "playlist" else ""
        prefix = "Channel" if source_type == "channel" else "Playlist" if source_type == "playlist" else "Source"
        if table and source_id:
            row = self.db.one(f"SELECT title FROM {table} WHERE id=? AND user_id=?", (source_id, user_id))
            if row:
                return f"{prefix} · {row['title']}"
        return f"{prefix} #{source_id}" if source_id else prefix

    def _target_label(self, user_id: str, target_type: str, target_id: int) -> str:
        if target_type == "video" and target_id:
            row = self.db.one("SELECT title FROM videos WHERE id=? AND user_id=?", (target_id, user_id))
            if row:
                return str(row["title"])
        return self._source_label(user_id, target_type, target_id) if target_type else ""

    def _source_video_count(self, user_id: str, source_type: str, source_id: int) -> int:
        if source_type == "channel":
            row = self.db.one(
                "SELECT COUNT(*) AS count FROM videos WHERE user_id=? AND channel_id=?", (user_id, source_id)
            )
        else:
            row = self.db.one(
                "SELECT COUNT(*) AS count FROM playlist_videos pv JOIN playlists p ON p.id=pv.playlist_id WHERE p.user_id=? AND p.id=?",
                (user_id, source_id),
            )
        return int((row or {}).get("count") or 0)

    def _source_history_limit(self, user_id: str, source_type: str, source_id: int) -> int:
        table = "channels" if source_type == "channel" else "playlists"
        row = self.db.one(f"SELECT history_limit FROM {table} WHERE id=? AND user_id=?", (source_id, user_id))
        if row and row.get("history_limit") is not None:
            return int(row["history_limit"])
        return int(self.personal_settings(user_id)["history_limit"])

    @staticmethod
    def _future_steps(phase: str) -> list[dict[str, str]]:
        steps: list[dict[str, str]] = []
        if phase == "discover":
            steps.append({"title": "New video metadata", "summary": "Batches will be built after checking sources."})
        if phase in {"discover", "metadata"}:
            steps.append(
                {
                    "title": "First historical batch",
                    "summary": "The priority source will be selected after processing new videos.",
                }
            )
        if phase in {"history_required", "history"}:
            steps.append(
                {
                    "title": "Following historical batches",
                    "summary": "Each source will be selected from local data and the remaining campaign time.",
                }
            )
        return steps

    def retry_job(self, user_id: str, job_id: int) -> dict[str, Any]:
        job = self.job(user_id, job_id)
        if job["status"] != "error":
            raise ConflictError("Only failed batches can be retried.")
        campaign = self.ensure_campaign(user_id)
        priority_row = self.db.one(
            "SELECT COALESCE(MAX(priority),0) AS value FROM agent_jobs WHERE user_id=? AND status='queued'",
            (user_id,),
        )
        with self.db.write() as connection:
            connection.execute(
                """UPDATE agent_jobs SET status='queued',attempts=0,error=NULL,started_at=NULL,finished_at=NULL,
                   available_at=?,manual=1,priority=? WHERE id=?""",
                (campaign["next_lot_at"], int((priority_row or {}).get("value", 0)) + 10, job_id),
            )
        return self.job(user_id, job_id)

    def delete_job(self, user_id: str, job_id: int) -> None:
        job = self.job(user_id, job_id)
        if job["status"] == "running":
            raise ConflictError("A running batch cannot be deleted.")
        with self.db.write() as connection:
            connection.execute("DELETE FROM agent_jobs WHERE id=? AND user_id=?", (job_id, user_id))

    def move_job(self, user_id: str, job_id: int, direction: str) -> dict[str, Any]:
        if direction not in {"up", "down"}:
            raise ValueError("Direction must be up or down.")
        jobs = self.db.all(
            "SELECT id,priority FROM agent_jobs WHERE user_id=? AND status='queued' ORDER BY priority DESC,created_at,id",
            (user_id,),
        )
        index = next((i for i, item in enumerate(jobs) if item["id"] == job_id), None)
        if index is None:
            raise NotFoundError("Queued batch not found.")
        other_index = index - 1 if direction == "up" else index + 1
        if 0 <= other_index < len(jobs):
            first, second = jobs[index], jobs[other_index]
            with self.db.write() as connection:
                connection.execute("UPDATE agent_jobs SET priority=? WHERE id=?", (second["priority"], first["id"]))
                connection.execute("UPDATE agent_jobs SET priority=? WHERE id=?", (first["priority"], second["id"]))
        return self.job(user_id, job_id)

    @staticmethod
    def _validate_playback(mode: str, quality: str, audio: str) -> None:
        if mode not in {"video", "audio"}:
            raise ValueError("Invalid playback mode.")
        if quality not in {"360", "480", "720", "1080", "best"}:
            raise ValueError("Invalid video quality.")
        if audio not in {"64", "96", "128", "192", "256"}:
            raise ValueError("Invalid audio quality.")

    def _nullable_playback(
        self, values: dict[str, Any], allow_history: bool = True
    ) -> tuple[str | None, str | None, str | None, int | None]:
        mode = str(values["mode"]) if values.get("mode") not in (None, "") else None
        quality = str(values["quality"]) if values.get("quality") not in (None, "") else None
        audio = str(values["audio_quality"]) if values.get("audio_quality") not in (None, "") else None
        if mode is not None or quality is not None or audio is not None:
            personal = {"default_mode": "video", "default_quality": "720", "default_audio_quality": "128"}
            self._validate_playback(
                mode or personal["default_mode"],
                quality or personal["default_quality"],
                audio or personal["default_audio_quality"],
            )
        history = None
        if allow_history and values.get("history_limit") not in (None, ""):
            history = int(values["history_limit"])
            if not 0 <= history <= 100000:
                raise ValueError("Invalid history limit.")
        return mode, quality, audio, history
