"""
Base abstract platform adapter.
"""

from abc import ABC, abstractmethod
from typing import Optional

try:
    from ..models import ResolvedContent
except (ImportError, ValueError):
    try:
        from .models import ResolvedContent
    except (ImportError, ValueError):
        from models import ResolvedContent


class BaseAdapter(ABC):
    """Abstract base class for platform adapters."""

    @classmethod
    @abstractmethod
    def can_handle(cls, url: str) -> bool:
        """Return True if this adapter can process the given URL."""
        pass

    @abstractmethod
    def resolve(self, url: str, tmp_dir: Optional[str] = None) -> ResolvedContent:
        """
        Extract metadata and native subtitles from URL.
        Returns a ResolvedContent object.
        """
        pass
