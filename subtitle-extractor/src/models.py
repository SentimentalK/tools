"""
Common data models for content metadata and resolved content.
"""

from dataclasses import dataclass, field
import datetime
from typing import Any, Dict, Optional


@dataclass
class ContentMetadata:
    source_type: str
    source_url: str
    canonical_url: Optional[str] = None
    source_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None
    published_at: Optional[str] = None
    duration_seconds: Optional[int | float] = None
    language: Optional[str] = None
    thumbnail_url: Optional[str] = None
    media_url: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int | str] = None
    comment_count: Optional[int | str] = None
    captured_at: Optional[str] = None
    platform_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.captured_at is None:
            self.captured_at = datetime.datetime.now().astimezone().isoformat()


@dataclass
class ResolvedContent:
    metadata: ContentMetadata
    transcript: Optional[str] = None
    transcript_status: str = "unavailable"  # "available", "unavailable", "failed"
    transcript_method: Optional[str] = None  # "subtitles", "auto-subtitles", "whisper-asr", None
