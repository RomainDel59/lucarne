"""Safe remote image download and local asset storage."""

from __future__ import annotations

import hashlib
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .errors import LucarneError

ALLOWED_IMAGE_HOSTS = {
    "i.ytimg.com",
    "yt3.ggpht.com",
    "yt3.googleusercontent.com",
    "ytimg.com",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def owner_key(user_id: str, identifier: int) -> str:
    """Return a filesystem-safe, opaque prefix for a user-owned asset."""
    user_digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:20]
    return f"{user_digest}-{identifier}"


def _validate_public_host(host: str) -> None:
    if host not in ALLOWED_IMAGE_HOSTS and not host.endswith(".ytimg.com"):
        raise LucarneError("The image host is not allowed.")
    for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise LucarneError("The image host does not resolve to a public address.")


def download_image(url: str, directory: Path, identifier: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise LucarneError("The image URL is invalid.")
    _validate_public_host(host)
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.get(url, headers={"User-Agent": "Lucarne/1.0"})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise LucarneError("The remote resource is not a supported image.")
        content = response.content
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise LucarneError("The image is empty or too large.")
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[content_type]
    digest = hashlib.sha256(content).hexdigest()[:16]
    file_name = f"{identifier}-{digest}{extension}"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / file_name
    destination.write_bytes(content)
    for old_file in directory.glob(f"{identifier}-*"):
        if old_file != destination:
            old_file.unlink(missing_ok=True)
    return file_name


def best_thumbnail(metadata: dict) -> str | None:
    candidates: list[tuple[int, str]] = []
    for item in metadata.get("thumbnails") or []:
        if not isinstance(item, dict) or not str(item.get("url", "")).startswith("https://"):
            continue
        area = int(item.get("width") or 0) * int(item.get("height") or 0)
        candidates.append((area, str(item["url"])))
    return max(candidates, default=(0, None))[1]
