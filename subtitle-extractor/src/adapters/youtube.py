"""
YouTube platform adapter wrapping yt-dlp.
"""

import os
import re
import tempfile
from typing import Optional

try:
    from .base import BaseAdapter
    from ..models import ContentMetadata, ResolvedContent
    from ..ytdlp import download_subtitles, fetch_metadata, parse_srt_to_paragraphs
except (ImportError, ValueError):
    try:
        from adapters.base import BaseAdapter
        from models import ContentMetadata, ResolvedContent
        from ytdlp import download_subtitles, fetch_metadata, parse_srt_to_paragraphs
    except (ImportError, ValueError):
        from base import BaseAdapter
        from models import ContentMetadata, ResolvedContent
        from ytdlp import download_subtitles, fetch_metadata, parse_srt_to_paragraphs


class YouTubeAdapter(BaseAdapter):
    """Adapter for YouTube URLs."""

    @classmethod
    def can_handle(cls, url: str) -> bool:
        lower = url.lower()
        return "youtube.com" in lower or "youtu.be" in lower

    def resolve(self, url: str, tmp_dir: Optional[str] = None) -> ResolvedContent:
        yt_args = [
            "--extractor-args", "youtube:player_client=android,web",
            "--remote-components", "ejs:github",
        ]
        data = fetch_metadata(url, extra_args=yt_args)
        
        source_id = data.get("id")
        if not source_id:
            m = re.search(r"[?&]v=([^&#]+)", url)
            if m:
                source_id = m.group(1)
            elif "youtu.be/" in url:
                source_id = url.split("youtu.be/")[-1].split("?")[0]
            else:
                source_id = ""

        title = data.get("title") or "YouTube_Video"
        creator = data.get("uploader") or data.get("channel") or data.get("uploader_id")
        
        pub_date = data.get("upload_date")
        if pub_date and len(pub_date) == 8:
            published_at = f"{pub_date[:4]}-{pub_date[4:6]}-{pub_date[6:8]}"
        else:
            published_at = None

        meta = ContentMetadata(
            source_type="youtube",
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

        # Subtitle extraction
        cleanup_tmp = False
        if not tmp_dir:
            tmp_dir = tempfile.mkdtemp(prefix="ytdlp_yt_")
            cleanup_tmp = True

        prefix = f"sub_{source_id or 'yt'}"
        sub_file, method = download_subtitles(url, tmp_dir, prefix, extra_args=yt_args)

        transcript = None
        status = "unavailable"
        if sub_file and os.path.exists(sub_file):
            paragraphs = parse_srt_to_paragraphs(sub_file)
            if paragraphs:
                transcript = paragraphs
                status = "available"
            try:
                os.remove(sub_file)
            except Exception:
                pass

        if cleanup_tmp:
            try:
                os.rmdir(tmp_dir)
            except Exception:
                pass

        return ResolvedContent(
            metadata=meta,
            transcript=transcript,
            transcript_status=status,
            transcript_method=method if transcript else None,
        )
