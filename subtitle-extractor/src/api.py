"""
Public Python API for Subtitle Extractor.

Exposes exactly two capabilities:
1. resolve_url(url: str) -> ContentMetadata
   Lightweight, read-only metadata lookup. Never accesses cookies, downloads media,
   or initializes ASR.
2. extract_url(url: str, ...) -> ResolvedContent
   Autonomous full content extraction (metadata -> native subtitles -> media/ASR fallback).
"""

from typing import Optional

try:
    from .models import ContentMetadata, ResolveError, ResolvedContent, UnsupportedURLError
    from .pipeline import Pipeline
except (ImportError, ValueError):
    from models import ContentMetadata, ResolveError, ResolvedContent, UnsupportedURLError
    from pipeline import Pipeline

__all__ = [
    "resolve_url",
    "extract_url",
    "ContentMetadata",
    "ResolvedContent",
    "ResolveError",
    "UnsupportedURLError",
]


def resolve_url(url: str) -> ContentMetadata:
    """
    Resolve lightweight, read-only metadata for any supported URL.

    - Performs platform detection and public metadata lookup.
    - Fast and read-only.
    - Never touches browser cookies, never downloads subtitles or media,
      never initializes ASR, and never touches .models/ or temporary buffers.

    Raises:
        UnsupportedURLError: If the URL platform is not supported.
        ResolveError: If metadata resolution fails.
    """
    pipeline = Pipeline()
    return pipeline.resolve_url(url)


def extract_url(
    url: str,
    browser_name: str = "chrome",
    profile_name: str = "Default",
) -> ResolvedContent:
    """
    Extract full content for any supported URL.

    - Completely self-contained: independently resolves the URL without requiring
      a prior resolve_url() call.
    - Checks for platform native subtitles first.
    - If native subtitles are unavailable, acquires media (reusing local browser
      auth state if necessary) and runs local FireRedASR2-AED offline speech recognition.
    - Returns ResolvedContent containing ContentMetadata and full transcript.

    Raises:
        UnsupportedURLError: If the URL platform is not supported.
        ResolveError: If metadata resolution fails.
    """
    pipeline = Pipeline(browser_name=browser_name, profile_name=profile_name)
    return pipeline.extract_url(url)
