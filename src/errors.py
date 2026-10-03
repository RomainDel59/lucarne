"""Domain exceptions converted to stable API errors."""


class LucarneError(RuntimeError):
    """Expected user-facing failure."""


class NotFoundError(LucarneError):
    """Requested resource does not exist for the active user."""


class ConflictError(LucarneError):
    """Requested operation conflicts with existing state."""


class YtDlpError(LucarneError):
    """yt-dlp failed. `reason` is the message in English, the language the failures are classified in."""

    def __init__(self, message: str, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason or message


class VideoUnavailableError(YtDlpError):
    """YouTube reports that a video cannot be accessed."""
