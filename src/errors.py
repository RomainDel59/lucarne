"""Domain exceptions converted to stable API errors."""


class LucarneError(RuntimeError):
    """Expected user-facing failure."""


class NotFoundError(LucarneError):
    """Requested resource does not exist for the active user."""


class ConflictError(LucarneError):
    """Requested operation conflicts with existing state."""


class VideoUnavailableError(LucarneError):
    """YouTube reports that a video cannot be accessed."""
