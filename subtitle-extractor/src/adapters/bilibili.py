"""
Bilibili platform adapter wrapping yt-dlp.
"""

import os
import re
from typing import Optional

try:
    from .base import BaseAdapter
    from ..models import ContentMetadata, ResolveError, TranscriptResult
    from ..ytdlp import download_subtitles, fetch_metadata, parse_srt_to_paragraphs
except (ImportError, ValueError):
    try:
        from adapters.base import BaseAdapter
        from models import ContentMetadata, ResolveError, TranscriptResult
        from ytdlp import download_subtitles, fetch_metadata, parse_srt_to_paragraphs
    except (ImportError, ValueError):
        from base import BaseAdapter
        from models import ContentMetadata, ResolveError, TranscriptResult
        from ytdlp import download_subtitles, fetch_metadata, parse_srt_to_paragraphs


class BilibiliAdapter(BaseAdapter):
    """Adapter for Bilibili URLs."""

    @classmethod
    def can_handle(cls, url: str) -> bool:
        lower = url.lower()
        return "bilibili.com" in lower or "b23.tv" in lower

    def resolve_metadata(self, url: str) -> ContentMetadata:
        """
        Lightweight metadata resolution for Bilibili.
        Fetches metadata JSON via yt-dlp without downloading media or subtitles.
        """
        try:
            data = fetch_metadata(url)
        except Exception as e:
            raise ResolveError(f"Bilibili metadata resolution failed for {url}: {e}") from e

        if not data or not isinstance(data, dict):
            raise ResolveError(f"Bilibili returned empty metadata for {url}")

        source_id = data.get("id")
        if not source_id:
            m = re.search(r"(BV[0-9A-Za-z]+)", url)
            if m:
                source_id = m.group(1)
            else:
                source_id = ""

        title = data.get("title") or "Bilibili_Video"
        creator = data.get("uploader") or data.get("uploader_id")

        pub_date = data.get("upload_date")
        if pub_date and len(pub_date) == 8:
            published_at = f"{pub_date[:4]}-{pub_date[4:6]}-{pub_date[6:8]}"
        else:
            published_at = None

        return ContentMetadata(
            source_type="bilibili",
            source_url=url,
            canonical_url=data.get("webpage_url") or url,
            source_id=source_id,
            title=title,
            description=data.get("description"),
            creator=creator,
            published_at=published_at,
            duration_seconds=data.get("duration"),
            thumbnail_url=data.get("thumbnail"),
            view_count=data.get("view_count"),
            like_count=data.get("like_count"),
            comment_count=data.get("comment_count"),
        )

    def try_get_native_transcript(
        self,
        url: str,
        metadata: ContentMetadata,
        tmp_dir: str,
    ) -> Optional[TranscriptResult]:
        """
        Attempt to download and parse native/AI subtitles.
        Returns TranscriptResult if available, otherwise None.
        """
        prefix = f"sub_{metadata.source_id or 'bili'}"
        sub_file, method = download_subtitles(url, tmp_dir, prefix)

        if sub_file and os.path.exists(sub_file):
            try:
                paragraphs = parse_srt_to_paragraphs(sub_file)
                if paragraphs:
                    return TranscriptResult(text=paragraphs, method=method or "subtitles")
            finally:
                if os.path.exists(sub_file):
                    try:
                        os.remove(sub_file)
                    except Exception:
                        pass

        return None
