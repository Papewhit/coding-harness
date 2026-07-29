"""Public API for the tinyconfig benchmark package."""

from .config import ConfigError, Settings, load_settings

__all__ = ["ConfigError", "Settings", "load_settings"]
