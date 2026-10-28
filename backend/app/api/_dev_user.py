"""Deprecated import compatibility; no dev-user bypass remains in runtime code."""

from app.core.auth import get_current_user as dev_current_user  # noqa: F401
