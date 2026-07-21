"""A tiny in-memory queue used by the local-repository benchmark."""

from .queue import Job, MiniQueue

__all__ = ["Job", "MiniQueue"]
