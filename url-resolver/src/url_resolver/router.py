"""
URL normalization, provider identification, stable ID extraction, and strategy router.
"""

import re
from urllib.parse import urlparse
from typing import Optional, Tuple
from .models import InvalidUrlError, ResolverValidationError, UnsupportedProtocolError
from .strategies.base import BaseStrategy
from .strategies.bilibili_wbi import BilibiliWbiStrategy
from .strategies.generic_static import GenericStaticStrategy
from .strategies.weixin_preview import WeixinPreviewStrategy


class ResolverRouter:
    """Routes URLs to appropriate resolution strategies and extracts stable identifiers."""

    def __init__(
        self,
        generic_strategy: Optional[BaseStrategy] = None,
        weixin_strategy: Optional[BaseStrategy] = None,
        bilibili_strategy: Optional[BaseStrategy] = None,
    ):
        self.generic_strategy = generic_strategy or GenericStaticStrategy()
        self.weixin_strategy = weixin_strategy or WeixinPreviewStrategy(fallback_strategy=self.generic_strategy)
        self.bilibili_strategy = bilibili_strategy or BilibiliWbiStrategy(fallback_strategy=self.generic_strategy)

    def validate_and_normalize(self, url: str) -> str:
        """Validates that URL is non-empty and has http/https scheme."""
        if not url or not isinstance(url, str) or not url.strip():
            raise InvalidUrlError("URL cannot be empty")

        trimmed = url.strip()
        parsed = urlparse(trimmed)

        if not parsed.scheme:
            raise InvalidUrlError(f"Missing URL scheme in: {trimmed}")

        if parsed.scheme.lower() not in ("http", "https"):
            raise UnsupportedProtocolError(f"Unsupported URL protocol '{parsed.scheme}'. Only http and https are supported.")

        if not parsed.netloc:
            raise InvalidUrlError(f"Invalid domain/host in URL: {trimmed}")

        return trimmed

    def identify(self, url: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Detects platform source_type, extracts stable source_id, and computes canonical URL.
        Returns: (source_type, source_id, canonical_url)
        """
        lower = url.lower()

        # WeChat Channels (微信视频号)
        if "weixin.qq.com/sph/" in lower or "channels.weixin.qq.com/finder-preview/" in lower:
            m = re.search(r"weixin\.qq\.com/sph/([A-Za-z0-9_-]+)", url)
            if not m:
                m = re.search(r"[?&]id=([A-Za-z0-9_-]+)", url)
            source_id = m.group(1) if m else None
            canonical_url = f"https://weixin.qq.com/sph/{source_id}" if source_id else url
            return "weixin", source_id, canonical_url

        # YouTube
        if "youtube.com" in lower or "youtu.be" in lower:
            source_id = None
            m = re.search(r"[?&]v=([A-Za-z0-9_-]+)", url)
            if m:
                source_id = m.group(1)
            elif "youtu.be/" in url:
                part = url.split("youtu.be/")[-1].split("?")[0].split("/")[0]
                if part:
                    source_id = part
            canonical_url = f"https://www.youtube.com/watch?v={source_id}" if source_id else url
            return "youtube", source_id, canonical_url

        # Bilibili
        if "bilibili.com" in lower or "b23.tv" in lower:
            m = re.search(r"(BV[0-9A-Za-z]+)", url)
            source_id = m.group(1) if m else None
            canonical_url = f"https://www.bilibili.com/video/{source_id}" if source_id else url
            return "bilibili", source_id, canonical_url

        # Generic web page
        return "web", None, url

    def route(self, url: str) -> BaseStrategy:
        """Selects strategy based on platform detection."""
        source_type, _, _ = self.identify(url)
        if source_type == "weixin":
            return self.weixin_strategy
        if source_type == "bilibili":
            return self.bilibili_strategy
        return self.generic_strategy
