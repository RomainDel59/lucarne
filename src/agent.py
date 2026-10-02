"""Persistent, rate-conscious catalogue agent."""

from __future__ import annotations

import json
import logging
import random
import threading
import time
from typing import Any

from .assets import best_thumbnail, download_image, owner_key
from .config import Settings
from .database import Database
from .errors import LucarneError, VideoUnavailableError
from .media import MediaService
from .repository import Repository, now
from .youtube import YouTubeClient

LOGGER = logging.getLogger("lucarne.agent")


class Agent:
    def __init__(
        self,
        config: Settings,
        database: Database,
        repository: Repository,
        youtube: YouTubeClient,
        media: MediaService,
    ) -> None:
        self.config = config
        self.db = database
        self.repository = repository
        self.youtube = youtube
        self.media = media
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.recover_interrupted()
        self.thread = threading.Thread(target=self._loop, name="lucarne-agent", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)

    def recover_interrupted(self) -> None:
        with self.db.write() as connection:
            count = connection.execute(
                """UPDATE agent_jobs SET status='queued',started_at=NULL,lease_until=NULL,error='Interrupted by restart'
                   WHERE status='running'"""
            ).rowcount
        if count:
            LOGGER.info("Requeued %s interrupted batch(es)", count)

    def _loop(self) -> None:
        cleanup_at = 0
        while not self.stop_event.wait(15):
            try:
                self.tick()
                if now() >= cleanup_at:
                    self.media.cleanup()
                    cleanup_at = now() + 900
            except Exception:
                LOGGER.exception("Unexpected agent loop failure")

    def tick(self) -> None:
        self._recover_stale()
        self._cleanup_jobs()
        users = self.db.all(
            """SELECT user_id FROM channels UNION SELECT user_id FROM playlists UNION
               SELECT user_id FROM agent_jobs UNION SELECT user_id FROM user_settings"""
        )
        for item in users:
            user_id = str(item["user_id"])
            campaign = self.repository.ensure_campaign(user_id)
            self._cancel_obsolete_history_jobs(user_id)
            self._prepare_automatic_jobs(user_id, campaign)
            if int(campaign["next_lot_at"]) > now():
                continue
            job = self.db.one(
                """SELECT * FROM agent_jobs WHERE user_id=? AND status='queued' AND available_at<=?
                   ORDER BY priority DESC,created_at,id LIMIT 1""",
                (user_id, now()),
            )
            if job:
                self._run(job, campaign)
                self._postpone(int(campaign["id"]), user_id)

    def _prepare_automatic_jobs(self, user_id: str, campaign: dict[str, Any]) -> None:
        settings = self.repository.instance_settings()
        batch_size = int(settings["batch_size"])
        campaign_id = int(campaign["id"])
        phase = str(campaign["phase"])
        sources = [
            {"type": "channel", "id": row["id"], "title": row["title"]}
            for row in self.repository.channels(user_id)
            if not str(row.get("external_id") or "").startswith("pending_")
        ]
        sources.extend(
            {"type": "playlist", "id": row["id"], "title": row["title"]}
            for row in self.repository.playlists(user_id)
            if row["kind"] == "youtube" and not str(row.get("external_id") or "").startswith("pending_")
        )
        if phase == "discover":
            if self._has_active(campaign_id, "discover"):
                return
            planned: set[str] = set()
            for job in self._campaign_jobs(campaign_id, "discover"):
                for source in json.loads(job["payload"] or "{}").get("sources", []):
                    planned.add(f"{source.get('type')}:{source.get('id')}")
            missing = [source for source in sources if f"{source['type']}:{source['id']}" not in planned]
            if missing:
                for offset in range(0, len(missing), batch_size):
                    self.repository.enqueue(
                        user_id,
                        "discover",
                        None,
                        None,
                        {"sources": missing[offset : offset + batch_size]},
                        manual=False,
                    )
                return
            self._set_phase(campaign_id, "metadata")
            phase = "metadata"
        if phase == "metadata":
            if self._has_active(campaign_id, "metadata"):
                return
            planned_ids: set[int] = set()
            for job in self._campaign_jobs(campaign_id, "metadata"):
                planned_ids.update(int(value) for value in json.loads(job["payload"] or "{}").get("candidate_ids", []))
            pending = self.db.all(
                "SELECT * FROM candidates WHERE user_id=? AND status='pending' ORDER BY priority DESC,created_at,id",
                (user_id,),
            )
            pending = [item for item in pending if int(item["id"]) not in planned_ids]
            if pending:
                for offset in range(0, len(pending), batch_size):
                    ids = [int(item["id"]) for item in pending[offset : offset + batch_size]]
                    self.repository.enqueue(user_id, "metadata", None, None, {"candidate_ids": ids}, manual=False)
                return
            self._set_phase(campaign_id, "history_required")
            phase = "history_required"
        if phase == "history_required":
            if self._has_active(campaign_id, "history"):
                return
            source = self._history_source(user_id)
            if source is None:
                self._finish_campaign(campaign_id, user_id)
                return
            self.repository.enqueue(
                user_id,
                "history",
                source["type"],
                int(source["id"]),
                {"source_type": source["type"], "source_id": source["id"], "limit": batch_size},
                manual=False,
            )
            return
        if phase == "history":
            if self._has_active(campaign_id, "history"):
                return
            campaign = self.db.one("SELECT * FROM campaigns WHERE id=?", (campaign_id,)) or campaign
            if max(now(), int(campaign["next_lot_at"])) >= int(campaign["deadline_at"]):
                self._finish_campaign(campaign_id, user_id)
                return
            source = self._history_source(user_id)
            if source is None:
                self._finish_campaign(campaign_id, user_id)
                return
            self.repository.enqueue(
                user_id,
                "history",
                source["type"],
                int(source["id"]),
                {"source_type": source["type"], "source_id": source["id"], "limit": batch_size},
                manual=False,
            )

    def _run(self, job: dict[str, Any], campaign: dict[str, Any]) -> None:
        job_id = int(job["id"])
        with self.db.write() as connection:
            connection.execute(
                "UPDATE agent_jobs SET status='running',started_at=?,lease_until=? WHERE id=?",
                (now(), now() + 7200, job_id),
            )
        LOGGER.info("Starting batch #%s (%s)", job_id, job["type"])
        try:
            payload = json.loads(job["payload"] or "{}")
            self._execute(str(job["user_id"]), str(job["type"]), job.get("target_type"), job.get("target_id"), payload)
            if job["type"] == "history" and campaign.get("phase") == "history_required":
                self._set_phase(int(campaign["id"]), "history")
            with self.db.write() as connection:
                connection.execute(
                    "UPDATE agent_jobs SET status='done',finished_at=?,lease_until=NULL,error=NULL WHERE id=?",
                    (now(), job_id),
                )
            LOGGER.info("Completed batch #%s", job_id)
        except VideoUnavailableError as error:
            with self.db.write() as connection:
                connection.execute(
                    "UPDATE agent_jobs SET status='done',finished_at=?,lease_until=NULL,error=NULL WHERE id=?",
                    (now(), job_id),
                )
            LOGGER.info("Skipped unavailable video in batch #%s: %s", job_id, error)
        except Exception as error:
            attempts = int(job["attempts"]) + 1
            status = "error" if attempts >= 3 else "queued"
            available = now() + min(3600, 60 * (2**attempts))
            with self.db.write() as connection:
                connection.execute(
                    """UPDATE agent_jobs SET status=?,attempts=?,error=?,lease_until=NULL,
                       started_at=CASE WHEN ?='queued' THEN NULL ELSE started_at END,
                       finished_at=CASE WHEN ?='error' THEN ? ELSE NULL END,available_at=? WHERE id=?""",
                    (status, attempts, str(error)[-4000:], status, status, now(), available, job_id),
                )
                if status == "error" and job.get("target_type") in {"channel", "playlist"} and job.get("target_id"):
                    table = "channels" if job["target_type"] == "channel" else "playlists"
                    connection.execute(
                        f"UPDATE {table} SET sync_status='error',sync_error=?,updated_at=? WHERE id=? AND user_id=?",
                        (str(error)[-2000:], now(), job["target_id"], job["user_id"]),
                    )
            if status == "error" and job["type"] == "history" and campaign.get("phase") == "history_required":
                self._set_phase(int(campaign["id"]), "history")
            LOGGER.warning("Batch #%s failed: %s", job_id, error)

    def _execute(
        self, user_id: str, job_type: str, target_type: str | None, target_id: int | None, payload: dict[str, Any]
    ) -> None:
        if job_type == "initialize_channel":
            self._initialize_channel(user_id, int(target_id or 0))
        elif job_type == "initialize_playlist":
            self._initialize_playlist(user_id, int(target_id or 0))
        elif job_type == "sync_source":
            self._discover_source(
                user_id,
                str(payload.get("source_type") or target_type or ""),
                int(payload.get("source_id") or target_id or 0),
            )
        elif job_type == "inspect_video":
            self._inspect_single_video(user_id, str(payload["url"]), payload.get("playlist_id"))
        elif job_type == "delete_channel":
            self._delete_channel(user_id, int(target_id or 0), bool(payload.get("delete_videos")))
        elif job_type == "delete_playlist":
            self._delete_playlist(user_id, int(target_id or 0), bool(payload.get("delete_videos")))
        elif job_type == "delete_video":
            self._delete_video(user_id, int(target_id or 0))
        elif job_type == "discover":
            sources = payload.get("sources", [])
            for index, source in enumerate(sources):
                self._discover_source(user_id, str(source["type"]), int(source["id"]))
                if index + 1 < len(sources):
                    time.sleep(random.randint(2, 6))
        elif job_type == "metadata":
            self._process_candidates(user_id, [int(value) for value in payload.get("candidate_ids", [])])
        elif job_type == "history":
            self._history(
                user_id,
                str(payload.get("source_type") or target_type or ""),
                int(payload.get("source_id") or target_id or 0),
                int(payload.get("limit", 10)),
            )

    def _initialize_channel(self, user_id: str, channel_id: int) -> None:
        channel = self.repository.channel(user_id, channel_id)
        language = self.repository.metadata_language()
        data = self.youtube.discover(str(channel["source_url"]), "channel", 1, 1, language)
        entries = data["entries"]
        if not entries:
            raise LucarneError("This channel does not contain any usable videos.")
        details, unavailable = self.youtube.inspect_batch([entries[0]["id"]], language)
        metadata = details[0] if details else {}
        external_id = data.get("id") or metadata.get("channel_id") or metadata.get("uploader_id")
        if not external_id:
            raise LucarneError("The YouTube channel could not be identified.")
        data = {
            **data,
            "id": external_id,
            "channel": data.get("channel") or metadata.get("channel"),
            "uploader": data.get("uploader") or metadata.get("uploader"),
        }
        self._update_source(user_id, "channel", channel_id, data)
        for item in details:
            self._store_metadata(user_id, item, channel_id=channel_id)
        self._mark_unavailable(user_id, unavailable)

    def _initialize_playlist(self, user_id: str, playlist_id: int) -> None:
        playlist = self.repository.playlist(user_id, playlist_id)
        language = self.repository.metadata_language()
        data = self.youtube.discover(str(playlist["source_url"]), "playlist", 1, 1, language)
        entries = data["entries"]
        if not entries:
            raise LucarneError("This playlist does not contain any usable videos.")
        self._update_source(user_id, "playlist", playlist_id, data)
        if entries:
            details, unavailable = self.youtube.inspect_batch([entries[0]["id"]], language)
            for metadata in details:
                video = self._store_metadata(user_id, metadata)
                self.repository.attach_video(user_id, playlist_id, int(video["id"]), entries[0].get("rank"))
            self._mark_unavailable(user_id, unavailable)

    def _inspect_single_video(self, user_id: str, url: str, playlist_id: int | None) -> None:
        video = self._store_metadata(user_id, self.youtube.inspect_video(url, self.repository.metadata_language()))
        if playlist_id:
            self.repository.attach_video(user_id, int(playlist_id), int(video["id"]))

    def _discover_source(self, user_id: str, source_type: str, source_id: int) -> None:
        source = (
            self.repository.channel(user_id, source_id)
            if source_type == "channel"
            else self.repository.playlist(user_id, source_id)
        )
        data = self.youtube.discover(
            str(source["source_url"]),
            source_type,
            1,
            int(self.repository.instance_settings()["batch_size"]),
            self.repository.metadata_language(),
        )
        self._update_source(user_id, source_type, source_id, data)
        local_priority = self._local_source_priority(user_id, source_type, source_id)
        for entry in data["entries"]:
            known = self.repository.video_by_youtube_id(user_id, str(entry["id"]))
            needs_playlist_link = False
            if source_type == "playlist" and known:
                needs_playlist_link = (
                    self.db.one(
                        "SELECT 1 AS found FROM playlist_videos WHERE playlist_id=? AND video_id=?",
                        (source_id, known["id"]),
                    )
                    is None
                )
            if source_type == "playlist" and known and not needs_playlist_link:
                # The video keeps the place YouTube gives it in the playlist.
                self.repository.attach_video(user_id, source_id, int(known["id"]), entry.get("rank"))
            if not known or needs_playlist_link:
                if not int(entry.get("timestamp") or 0):
                    entry = {**entry, "timestamp": local_priority}
                self._add_candidate(user_id, source_type, source_id, entry)

    def _local_source_priority(self, user_id: str, source_type: str, source_id: int) -> int:
        if source_type == "channel":
            row = self.db.one(
                "SELECT MAX(published_at) AS value FROM videos WHERE user_id=? AND channel_id=?",
                (user_id, source_id),
            )
        else:
            row = self.db.one(
                """SELECT MAX(v.published_at) AS value FROM playlist_videos pv JOIN videos v ON v.id=pv.video_id
                   WHERE pv.playlist_id=? AND v.user_id=?""",
                (source_id, user_id),
            )
        return int((row or {}).get("value") or 0)

    def _process_candidates(self, user_id: str, candidate_ids: list[int]) -> None:
        if not candidate_ids:
            return
        marks = ",".join("?" for _ in candidate_ids)
        candidates = self.db.all(
            f"SELECT * FROM candidates WHERE user_id=? AND id IN ({marks}) ORDER BY priority DESC,created_at,id",
            tuple([user_id, *candidate_ids]),
        )
        if not candidates:
            return
        details, unavailable = self.youtube.inspect_batch(
            [str(item["youtube_id"]) for item in candidates], self.repository.metadata_language()
        )
        by_id = {str(item["id"]): item for item in details}
        for candidate in candidates:
            metadata = by_id.get(str(candidate["youtube_id"]))
            if metadata:
                channel_id = int(candidate["source_id"]) if candidate["source_type"] == "channel" else None
                video = self._store_metadata(user_id, metadata, channel_id)
                if candidate["source_type"] == "playlist":
                    self.repository.attach_video(
                        user_id, int(candidate["source_id"]), int(video["id"]), candidate["source_rank"]
                    )
        self._mark_unavailable(user_id, unavailable)
        with self.db.write() as connection:
            for item in candidates:
                status = "done" if str(item["youtube_id"]) in by_id else "unavailable"
                connection.execute("UPDATE candidates SET status=? WHERE id=?", (status, item["id"]))

    def _history_source(self, user_id: str) -> dict[str, Any] | None:
        sources: list[tuple[int, dict[str, Any]]] = []
        personal_limit = int(self.repository.personal_settings(user_id)["history_limit"])
        for channel in self.repository.channels(user_id):
            if str(channel.get("external_id") or "").startswith("pending_"):
                continue
            cap = channel["history_limit"] if channel["history_limit"] is not None else personal_limit
            if channel["source_exhausted"] or (cap and channel["video_count"] >= cap):
                continue
            frontier = self.db.one(
                "SELECT MIN(published_at) AS value FROM videos WHERE user_id=? AND channel_id=? AND deleting=0",
                (user_id, channel["id"]),
            )
            sources.append((int((frontier or {}).get("value") or 2**62), {"type": "channel", **channel}))
        for playlist in self.repository.playlists(user_id):
            if playlist["kind"] != "youtube" or str(playlist.get("external_id") or "").startswith("pending_"):
                continue
            cap = playlist["history_limit"] if playlist["history_limit"] is not None else personal_limit
            if playlist["source_exhausted"] or (cap and playlist["video_count"] >= cap):
                continue
            frontier = self.db.one(
                """SELECT MIN(v.published_at) AS value FROM playlist_videos pv JOIN videos v ON v.id=pv.video_id
                   WHERE pv.playlist_id=? AND v.user_id=? AND v.deleting=0""",
                (playlist["id"], user_id),
            )
            sources.append((int((frontier or {}).get("value") or 2**62), {"type": "playlist", **playlist}))
        if not sources:
            return None
        return max(sources, key=lambda item: item[0])[1]

    def _history(self, user_id: str, source_type: str, source_id: int, limit: int) -> None:
        source = (
            self.repository.channel(user_id, source_id)
            if source_type == "channel"
            else self.repository.playlist(user_id, source_id)
        )
        personal_limit = int(self.repository.personal_settings(user_id)["history_limit"])
        cap = source["history_limit"] if source["history_limit"] is not None else personal_limit
        if source_type == "channel":
            known = self.db.one(
                "SELECT COUNT(*) AS count FROM videos WHERE user_id=? AND channel_id=?", (user_id, source_id)
            )
        else:
            known = self.db.one("SELECT COUNT(*) AS count FROM playlist_videos WHERE playlist_id=?", (source_id,))
        remaining = max(0, int(cap) - int((known or {}).get("count", 0))) if cap else limit
        limit = min(limit, remaining) if cap else limit
        if limit <= 0:
            return
        start = int(source["catalog_offset"]) + 1
        language = self.repository.metadata_language()
        data = self.youtube.discover(str(source["source_url"]), source_type, start, limit, language)
        details, unavailable = self.youtube.inspect_batch([str(item["id"]) for item in data["entries"]], language)
        ranks = {str(item["id"]): item.get("rank") for item in data["entries"]}
        for metadata in details:
            video = self._store_metadata(user_id, metadata, int(source["id"]) if source_type == "channel" else None)
            if source_type == "playlist":
                self.repository.attach_video(
                    user_id, int(source["id"]), int(video["id"]), ranks.get(str(video["youtube_id"]))
                )
        self._mark_unavailable(user_id, unavailable)
        self._update_source(user_id, source_type, int(source["id"]), data)

    def _store_metadata(self, user_id: str, metadata: dict[str, Any], channel_id: int | None = None) -> dict[str, Any]:
        video = self.repository.store_video(user_id, metadata, channel_id)
        preferred_url = best_thumbnail(metadata)
        fallback_url = f"https://i.ytimg.com/vi/{video['youtube_id']}/hqdefault.jpg"
        urls = list(dict.fromkeys(value for value in (preferred_url, fallback_url) if value))
        for index, url in enumerate(urls):
            try:
                file_name = download_image(url, self.config.thumbnails, owner_key(user_id, int(video["id"])))
                with self.db.write() as connection:
                    connection.execute(
                        "UPDATE videos SET thumbnail_file=?,updated_at=? WHERE id=?", (file_name, now(), video["id"])
                    )
                video["thumbnail_file"] = file_name
                break
            except Exception as error:
                if index + 1 == len(urls):
                    LOGGER.info("Could not cache thumbnail for video %s: %s", video["id"], error)
        return video

    def _update_source(self, user_id: str, source_type: str, source_id: int, data: dict[str, Any]) -> None:
        timestamp = now()
        # A channel is named after its author, but YouTube gives a playlist the name of its owner in the same
        # fields: a playlist keeps its own title.
        names = ("channel", "uploader", "title") if source_type == "channel" else ("title", "channel", "uploader")
        title = str(next((data[name] for name in names if data.get(name)), ""))[:255]
        image_file = None
        has_remote_image = bool(data.get("image_url"))
        if has_remote_image:
            try:
                directory = self.config.channel_images if source_type == "channel" else self.config.playlist_images
                image_file = download_image(str(data["image_url"]), directory, owner_key(user_id, source_id))
            except Exception as error:
                LOGGER.info("Could not cache %s image %s: %s", source_type, source_id, error)
        else:
            directory = self.config.channel_images if source_type == "channel" else self.config.playlist_images
            for file in directory.glob(f"{owner_key(user_id, source_id)}-*"):
                file.unlink(missing_ok=True)
        table = "channels" if source_type == "channel" else "playlists"
        with self.db.write() as connection:
            if source_type == "channel":
                connection.execute(
                    f"""UPDATE {table} SET title=COALESCE(NULLIF(?,''),title),external_id=COALESCE(?,external_id),
                       image_file=CASE WHEN ?=0 THEN NULL ELSE COALESCE(?,image_file) END,
                       image_updated_at=CASE WHEN ?=0 THEN NULL WHEN ? IS NULL THEN image_updated_at ELSE ? END,
                       catalog_offset=MAX(catalog_offset,?),source_exhausted=?,sync_status='idle',sync_error=NULL,
                       synced_at=?,updated_at=? WHERE id=? AND user_id=?""",
                    (
                        title,
                        data.get("id"),
                        int(has_remote_image),
                        image_file,
                        int(has_remote_image),
                        image_file,
                        timestamp,
                        int(data.get("next_offset") or 0),
                        int(not data.get("has_more", False)),
                        timestamp,
                        timestamp,
                        source_id,
                        user_id,
                    ),
                )
            else:
                connection.execute(
                    f"""UPDATE {table} SET title=COALESCE(NULLIF(?,''),title),external_id=COALESCE(?,external_id),
                       image_file=CASE WHEN ?=0 THEN NULL ELSE COALESCE(?,image_file) END,
                       catalog_offset=MAX(catalog_offset,?),source_exhausted=?,
                       sync_status='idle',sync_error=NULL,updated_at=? WHERE id=? AND user_id=?""",
                    (
                        title,
                        data.get("id"),
                        int(has_remote_image),
                        image_file,
                        int(data.get("next_offset") or 0),
                        int(not data.get("has_more", False)),
                        timestamp,
                        source_id,
                        user_id,
                    ),
                )

    def _add_candidate(self, user_id: str, source_type: str, source_id: int, entry: dict[str, Any]) -> None:
        with self.db.write() as connection:
            connection.execute(
                """INSERT INTO candidates(user_id,source_type,source_id,youtube_id,priority,status,source_rank,created_at)
                   VALUES (?,?,?,?,?,'pending',?,?)
                   ON CONFLICT(user_id,source_type,source_id,youtube_id) DO UPDATE SET
                     priority=excluded.priority,source_rank=excluded.source_rank,
                     status=CASE WHEN candidates.status='unavailable' THEN 'pending' ELSE candidates.status END""",
                (
                    user_id,
                    source_type,
                    source_id,
                    str(entry["id"]),
                    int(entry.get("timestamp") or 0),
                    entry.get("rank"),
                    now(),
                ),
            )

    def _mark_unavailable(self, user_id: str, youtube_ids: list[str]) -> None:
        if not youtube_ids:
            return
        LOGGER.info(
            "Skipped %s unavailable YouTube video(s): %s",
            len(youtube_ids),
            ", ".join(sorted(set(youtube_ids))),
        )
        with self.db.write() as connection:
            connection.executemany(
                """UPDATE videos SET availability='unavailable',unavailable_reason=?,availability_checked_at=?,updated_at=?
                   WHERE user_id=? AND youtube_id=?""",
                [
                    (
                        "This video is private, deleted, or temporarily unavailable on YouTube.",
                        now(),
                        now(),
                        user_id,
                        value,
                    )
                    for value in youtube_ids
                ],
            )

    def _delete_channel(self, user_id: str, channel_id: int, delete_videos: bool) -> None:
        self._cancel_target_jobs(user_id, "channel", channel_id)
        self.repository.channel(user_id, channel_id)
        if delete_videos:
            video_ids = self.db.all("SELECT id FROM videos WHERE user_id=? AND channel_id=?", (user_id, channel_id))
            for item in video_ids:
                self.media.delete_video_files(user_id, int(item["id"]))
            with self.db.write() as connection:
                connection.execute("DELETE FROM videos WHERE user_id=? AND channel_id=?", (user_id, channel_id))
            with self.db.write() as connection:
                connection.execute("DELETE FROM channels WHERE id=? AND user_id=?", (channel_id, user_id))
            for file in self.config.channel_images.glob(f"{owner_key(user_id, channel_id)}-*"):
                file.unlink(missing_ok=True)
        else:
            self.repository.unsubscribe_channel(user_id, channel_id)

    def _delete_playlist(self, user_id: str, playlist_id: int, delete_videos: bool) -> None:
        self._cancel_target_jobs(user_id, "playlist", playlist_id)
        self.repository.playlist(user_id, playlist_id)
        if delete_videos:
            video_ids = self.db.all("SELECT video_id AS id FROM playlist_videos WHERE playlist_id=?", (playlist_id,))
            for item in video_ids:
                self.media.delete_video_files(user_id, int(item["id"]))
            with self.db.write() as connection:
                connection.executemany(
                    "DELETE FROM videos WHERE id=? AND user_id=?", [(item["id"], user_id) for item in video_ids]
                )
        with self.db.write() as connection:
            connection.execute("DELETE FROM playlists WHERE id=? AND user_id=?", (playlist_id, user_id))
        for file in self.config.playlist_images.glob(f"{owner_key(user_id, playlist_id)}-*"):
            file.unlink(missing_ok=True)

    def _delete_video(self, user_id: str, video_id: int) -> None:
        self._cancel_target_jobs(user_id, "video", video_id)
        self.media.delete_video_files(user_id, video_id)
        self.repository.delete_video(user_id, video_id)

    def _cancel_target_jobs(self, user_id: str, target_type: str, target_id: int) -> None:
        discover_jobs = self.db.all(
            "SELECT id,payload FROM agent_jobs WHERE user_id=? AND type='discover' AND status='queued'",
            (user_id,),
        )
        with self.db.write() as connection:
            connection.execute(
                """UPDATE agent_jobs SET status='cancelled',finished_at=?
                   WHERE user_id=? AND target_type=? AND target_id=? AND status='queued'""",
                (now(), user_id, target_type, target_id),
            )
            connection.execute(
                "DELETE FROM candidates WHERE user_id=? AND source_type=? AND source_id=?",
                (user_id, target_type, target_id),
            )
            for job in discover_jobs:
                payload = json.loads(job["payload"] or "{}")
                sources = [
                    source
                    for source in payload.get("sources", [])
                    if not (str(source.get("type")) == target_type and int(source.get("id") or 0) == target_id)
                ]
                if sources:
                    payload["sources"] = sources
                    connection.execute(
                        "UPDATE agent_jobs SET payload=? WHERE id=?",
                        (json.dumps(payload, ensure_ascii=False, sort_keys=True), job["id"]),
                    )
                else:
                    connection.execute(
                        "UPDATE agent_jobs SET status='cancelled',finished_at=? WHERE id=?", (now(), job["id"])
                    )

    def _postpone(self, campaign_id: int, user_id: str) -> None:
        settings = self.repository.instance_settings()
        delay = self.repository.randomized_wait(int(settings["lot_wait_seconds"]))
        timestamp = now()
        queued = self.db.one(
            "SELECT COUNT(*) AS count FROM agent_jobs WHERE campaign_id=? AND status IN ('queued','running')",
            (campaign_id,),
        )
        if int((queued or {}).get("count", 0)) == 0:
            self._prepare_automatic_jobs(
                user_id, self.db.one("SELECT * FROM campaigns WHERE id=?", (campaign_id,)) or {}
            )
            queued = self.db.one(
                "SELECT COUNT(*) AS count FROM agent_jobs WHERE campaign_id=? AND status IN ('queued','running')",
                (campaign_id,),
            )
        if int((queued or {}).get("count", 0)) == 0:
            return
        with self.db.write() as connection:
            connection.execute(
                "UPDATE campaigns SET next_lot_at=?,updated_at=? WHERE id=?",
                (timestamp + delay, timestamp, campaign_id),
            )

    def _has_active(self, campaign_id: int, job_type: str) -> bool:
        row = self.db.one(
            "SELECT COUNT(*) AS count FROM agent_jobs WHERE campaign_id=? AND type=? AND status IN ('queued','running')",
            (campaign_id, job_type),
        )
        return bool(int((row or {}).get("count", 0)))

    def _campaign_jobs(self, campaign_id: int, job_type: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM agent_jobs WHERE campaign_id=? AND type=?", (campaign_id, job_type))

    def _set_phase(self, campaign_id: int, phase: str) -> None:
        with self.db.write() as connection:
            connection.execute("UPDATE campaigns SET phase=?,updated_at=? WHERE id=?", (phase, now(), campaign_id))

    def _finish_campaign(self, campaign_id: int, user_id: str) -> None:
        pending = self.db.one(
            "SELECT COUNT(*) AS count FROM agent_jobs WHERE campaign_id=? AND status IN ('queued','running')",
            (campaign_id,),
        )
        if int((pending or {}).get("count", 0)):
            return
        timestamp = now()
        with self.db.write() as connection:
            connection.execute(
                "UPDATE campaigns SET status='done',finished_at=?,updated_at=? WHERE id=?",
                (timestamp, timestamp, campaign_id),
            )
        self.repository.ensure_campaign(user_id)

    def _cancel_obsolete_history_jobs(self, user_id: str) -> None:
        jobs = self.db.all(
            "SELECT * FROM agent_jobs WHERE user_id=? AND type='history' AND status IN ('queued','error')", (user_id,)
        )
        personal_limit = int(self.repository.personal_settings(user_id)["history_limit"])
        for job in jobs:
            try:
                source_type = str(job["target_type"] or "")
                source_id = int(job["target_id"] or 0)
                source = (
                    self.repository.channel(user_id, source_id)
                    if source_type == "channel"
                    else self.repository.playlist(user_id, source_id)
                )
                limit = source["history_limit"] if source["history_limit"] is not None else personal_limit
                if not limit:
                    continue
                if source_type == "channel":
                    count = self.db.one(
                        "SELECT COUNT(*) AS count FROM videos WHERE user_id=? AND channel_id=?", (user_id, source_id)
                    )
                else:
                    count = self.db.one(
                        "SELECT COUNT(*) AS count FROM playlist_videos WHERE playlist_id=?", (source_id,)
                    )
                if int((count or {}).get("count", 0)) < int(limit):
                    continue
                with self.db.write() as connection:
                    connection.execute("DELETE FROM agent_jobs WHERE id=?", (job["id"],))
            except Exception as error:
                LOGGER.debug("Could not prune history batch %s: %s", job["id"], error)
                continue

    def _recover_stale(self) -> None:
        with self.db.write() as connection:
            connection.execute(
                """UPDATE agent_jobs SET status='queued',started_at=NULL,lease_until=NULL,error='Interrupted batch'
                   WHERE status='running' AND lease_until IS NOT NULL AND lease_until<?""",
                (now(),),
            )

    def _cleanup_jobs(self) -> None:
        with self.db.write() as connection:
            connection.execute(
                "DELETE FROM agent_jobs WHERE status IN ('done','cancelled') AND finished_at IS NOT NULL AND finished_at<?",
                (now() - 7 * 86400,),
            )
