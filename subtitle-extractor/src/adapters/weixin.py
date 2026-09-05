"""
WeChat Channels (微信视频号) platform adapter using direct anonymous preview API.
"""

import datetime
import re
from typing import Optional
import httpx

try:
    from .base import BaseAdapter
    from ..models import ContentMetadata, ResolvedContent
except (ImportError, ValueError):
    try:
        from adapters.base import BaseAdapter
        from models import ContentMetadata, ResolvedContent
    except (ImportError, ValueError):
        from base import BaseAdapter
        from models import ContentMetadata, ResolvedContent


class WeixinAdapter(BaseAdapter):
    """Adapter for WeChat Channels (微信视频号) SPH links."""

    API_URL = "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info"

    @classmethod
    def can_handle(cls, url: str) -> bool:
        lower = url.lower()
        return "weixin.qq.com/sph/" in lower or "channels.weixin.qq.com/finder-preview/" in lower

    @classmethod
    def extract_short_uri(cls, url: str) -> str:
        """Extract the SPH identifier from various URL structures."""
        m = re.search(r"weixin\.qq\.com/sph/([A-Za-z0-9_-]+)", url)
        if m:
            return m.group(1)
        m = re.search(r"[?&]id=([A-Za-z0-9_-]+)", url)
        if m:
            return m.group(1)
        return ""

    def resolve(self, url: str, tmp_dir: Optional[str] = None) -> ResolvedContent:
        short_uri = self.extract_short_uri(url)
        if not short_uri:
            # Fallback metadata when ID cannot be extracted
            meta = ContentMetadata(
                source_type="weixin",
                source_url=url,
                title="Weixin_Channels_Video",
            )
            return ResolvedContent(
                metadata=meta,
                transcript_status="failed",
            )

        headers = {
            "Content-Type": "application/json",
            "Referer": f"https://channels.weixin.qq.com/finder-preview/pages/sph?id={short_uri}",
            "Origin": "https://channels.weixin.qq.com",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        payload = {
            "baseReq": {"generalToken": ""},
            "shortUri": short_uri,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self.API_URL, headers=headers, json=payload)
                data = resp.json()
        except Exception as e:
            # Network or parsing failure
            meta = ContentMetadata(
                source_type="weixin",
                source_url=url,
                source_id=short_uri,
                title="Weixin_Channels_Video",
                platform_metadata={"error": str(e)},
            )
            return ResolvedContent(
                metadata=meta,
                transcript_status="failed",
            )

        return self.parse_api_response(url, short_uri, data)

    @classmethod
    def parse_api_response(cls, url: str, short_uri: str, data: dict) -> ResolvedContent:
        """Parse get_feed_info response dictionary into ResolvedContent."""
        data_block = data.get("data", {}) if isinstance(data, dict) else {}
        author_info = data_block.get("authorInfo") or {}
        feed_info = data_block.get("feedInfo") or {}
        scene_info = data_block.get("sceneInfo") or {}

        creator = author_info.get("nickname") or None
        description = feed_info.get("description") or None

        # Determine readable title from description or fallback
        if description and description.strip():
            title = description.strip().split("\n")[0][:80]
        else:
            title = f"微信视频号_{short_uri}"

        # Parse create time
        createtime = feed_info.get("createtime")
        if createtime and isinstance(createtime, (int, float)):
            try:
                published_at = datetime.datetime.fromtimestamp(createtime, datetime.timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                published_at = None
        else:
            published_at = None

        cover_url = feed_info.get("coverUrl") or None
        like_count = feed_info.get("likeCountFmt") or None
        comment_count = feed_info.get("commentCountFmt") or None

        platform_meta = {}
        if feed_info.get("favCountFmt"):
            platform_meta["fav_count"] = feed_info["favCountFmt"]
        if feed_info.get("forwardCountFmt"):
            platform_meta["forward_count"] = feed_info["forwardCountFmt"]
        if scene_info.get("dynamicExportId"):
            platform_meta["dynamic_export_id"] = scene_info["dynamicExportId"]
        if author_info.get("headImgUrl"):
            platform_meta["author_avatar"] = author_info["headImgUrl"]

        meta = ContentMetadata(
            source_type="weixin",
            source_url=url,
            canonical_url=f"https://weixin.qq.com/sph/{short_uri}",
            source_id=short_uri,
            title=title,
            description=description,
            creator=creator,
            published_at=published_at,
            thumbnail_url=cover_url,
            like_count=like_count,
            comment_count=comment_count,
            platform_metadata=platform_meta if platform_meta else None,
        )

        # WeChat Channels has no public native separate timed subtitle tracks
        return ResolvedContent(
            metadata=meta,
            transcript=None,
            transcript_status="unavailable",
            transcript_method=None,
        )
