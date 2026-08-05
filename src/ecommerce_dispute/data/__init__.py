"""Read-only access to the Olist source tables."""

from .repository import DataIntegrityError, OlistRepository

__all__ = ["DataIntegrityError", "OlistRepository"]
