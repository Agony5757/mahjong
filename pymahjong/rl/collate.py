"""Collation functions for batching observations."""

from .cached_dataset import cached_event_collate  # noqa: F401

__all__ = ["cached_event_collate"]
