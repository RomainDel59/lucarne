"""Runtime configuration and persistent paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_id: str
    storage: Path
    database: Path
    thumbnails: Path
    channel_images: Path
    playlist_images: Path
    downloads: Path
    library: Path

    @classmethod
    def load(cls) -> Settings:
        storage = Path(os.getenv("APP_PERSISTENT_STORAGE", "/tmp/lucarne-data")).resolve()
        return cls(
            app_id=os.getenv("APP_ID", "lucarne"),
            storage=storage,
            database=storage / "lucarne.db",
            thumbnails=storage / "thumbnails",
            channel_images=storage / "channel-images",
            playlist_images=storage / "playlist-images",
            downloads=storage / "downloads",
            library=storage / "library",
        )

    def create_directories(self) -> None:
        for path in (
            self.storage,
            self.thumbnails,
            self.channel_images,
            self.playlist_images,
            self.downloads,
            self.library,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings.load()
