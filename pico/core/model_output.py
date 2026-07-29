"""Removed legacy model-output parser tombstone.

Runtime consumes provider-neutral structured responses.  This module remains
only so stale third-party imports fail clearly instead of silently enabling a
text-protocol fallback.
"""
