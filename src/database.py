"""SQLite persistence for Lucarne."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 4


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    default_mode TEXT NOT NULL DEFAULT 'video',
    default_quality TEXT NOT NULL DEFAULT '720',
    default_audio_quality TEXT NOT NULL DEFAULT '128',
    history_limit INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS instance_settings (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    batch_size INTEGER NOT NULL DEFAULT 10,
    lot_wait_seconds INTEGER NOT NULL DEFAULT 300,
    campaign_duration_seconds INTEGER NOT NULL DEFAULT 7200,
    temporary_retention_days INTEGER NOT NULL DEFAULT 7,
    metadata_language TEXT,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    external_id TEXT,
    title TEXT NOT NULL,
    image_file TEXT,
    image_updated_at INTEGER,
    mode TEXT,
    quality TEXT,
    audio_quality TEXT,
    history_limit INTEGER,
    catalog_offset INTEGER NOT NULL DEFAULT 0,
    source_exhausted INTEGER NOT NULL DEFAULT 0,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    sync_error TEXT,
    synced_at INTEGER,
    subscribed INTEGER NOT NULL DEFAULT 1,
    deleting INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE (user_id, source_url)
);

CREATE TABLE IF NOT EXISTS channel_catalogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE (user_id, normalized_name)
);

CREATE TABLE IF NOT EXISTS channel_catalog_memberships (
    catalog_id INTEGER NOT NULL REFERENCES channel_catalogs(id) ON DELETE CASCADE,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    PRIMARY KEY (catalog_id, channel_id)
);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT,
    external_id TEXT,
    kind TEXT NOT NULL DEFAULT 'personal',
    image_file TEXT,
    mode TEXT,
    quality TEXT,
    audio_quality TEXT,
    history_limit INTEGER,
    catalog_offset INTEGER NOT NULL DEFAULT 0,
    source_exhausted INTEGER NOT NULL DEFAULT 0,
    sync_status TEXT NOT NULL DEFAULT 'idle',
    sync_error TEXT,
    deleting INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE (user_id, source_url)
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    youtube_id TEXT NOT NULL,
    webpage_url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
    channel_name TEXT NOT NULL DEFAULT '',
    published_at INTEGER NOT NULL DEFAULT 0,
    duration INTEGER NOT NULL DEFAULT 0,
    thumbnail_file TEXT,
    mode TEXT,
    quality TEXT,
    audio_quality TEXT,
    availability TEXT NOT NULL DEFAULT 'available',
    unavailable_reason TEXT,
    availability_checked_at INTEGER,
    retained INTEGER NOT NULL DEFAULT 0,
    deleting INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE (user_id, youtube_id)
);

CREATE TABLE IF NOT EXISTS playlist_videos (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    added_at INTEGER NOT NULL,
    PRIMARY KEY (playlist_id, video_id)
);

CREATE TABLE IF NOT EXISTS histories (
    user_id TEXT NOT NULL,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    position REAL NOT NULL DEFAULT 0,
    duration REAL,
    completed INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, video_id)
);

CREATE TABLE IF NOT EXISTS downloads (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    quality TEXT NOT NULL,
    audio_quality TEXT NOT NULL,
    status TEXT NOT NULL,
    file_name TEXT,
    media_id TEXT,
    mime_type TEXT,
    size INTEGER,
    retained INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at INTEGER NOT NULL,
    accessed_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    youtube_id TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    source_rank INTEGER,
    created_at INTEGER NOT NULL,
    UNIQUE (user_id, source_type, source_id, youtube_id)
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    phase TEXT NOT NULL DEFAULT 'discover',
    source_cursor INTEGER NOT NULL DEFAULT 0,
    started_at INTEGER NOT NULL,
    deadline_at INTEGER NOT NULL,
    next_lot_at INTEGER NOT NULL,
    finished_at INTEGER,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
    type TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    manual INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at INTEGER NOT NULL,
    started_at INTEGER,
    finished_at INTEGER,
    lease_until INTEGER,
    error TEXT,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_channels_user ON channels(user_id, deleting, title);
CREATE INDEX IF NOT EXISTS idx_videos_user_date ON videos(user_id, published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_playlist_videos_video ON playlist_videos(video_id);
CREATE INDEX IF NOT EXISTS idx_downloads_lookup ON downloads(user_id, video_id, mode, quality, audio_quality, status);
CREATE INDEX IF NOT EXISTS idx_candidates_queue ON candidates(user_id, priority DESC, created_at, id);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_queue ON agent_jobs(user_id, status, priority DESC, available_at, id);
CREATE INDEX IF NOT EXISTS idx_campaigns_active ON campaigns(user_id, status, id DESC);
"""


class Database:
    """Small thread-safe connection factory with explicit transactions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._write_lock = threading.RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.write() as connection:
            connection.executescript(SCHEMA)
            row = connection.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
            if row is None:
                connection.execute("INSERT INTO schema_meta(version) VALUES (?)", (SCHEMA_VERSION,))
            else:
                version = int(row["version"])
                if version == 1:
                    connection.execute("ALTER TABLE channels ADD COLUMN subscribed INTEGER NOT NULL DEFAULT 1")
                    connection.execute("ALTER TABLE videos ADD COLUMN unavailable_reason TEXT")
                    connection.execute("ALTER TABLE videos ADD COLUMN availability_checked_at INTEGER")
                    connection.execute("ALTER TABLE videos ADD COLUMN deleting INTEGER NOT NULL DEFAULT 0")
                    connection.execute("ALTER TABLE candidates ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
                    version = 2
                if version == 2:
                    connection.execute("ALTER TABLE instance_settings ADD COLUMN metadata_language TEXT")
                    version = 3
                if version == 3:
                    connection.execute("ALTER TABLE candidates ADD COLUMN source_rank INTEGER")
                    version = 4
                if version != SCHEMA_VERSION:
                    raise RuntimeError(f"Unsupported database schema version: {row['version']}")
                if int(row["version"]) != SCHEMA_VERSION:
                    connection.execute("UPDATE schema_meta SET version=?", (SCHEMA_VERSION,))

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        with self._write_lock:
            connection = self.connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def one(self, query: str, parameters: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.read() as connection:
            row = connection.execute(query, parameters).fetchone()
            return dict(row) if row else None

    def all(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.read() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def placeholders(values: list[Any]) -> str:
    return ",".join("?" for _ in values)
