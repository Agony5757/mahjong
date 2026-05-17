"""Auto-register all encoding strategies on import."""

from . import v1, v2, v3, v4  # noqa: F401 -- triggers register() calls
