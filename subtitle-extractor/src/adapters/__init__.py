"""
Platform adapter registry and exports.
"""

try:
    from .base import BaseAdapter
    from .youtube import YouTubeAdapter
    from .bilibili import BilibiliAdapter
    from .weixin import WeixinAdapter
except (ImportError, ValueError):
    from base import BaseAdapter
    from youtube import YouTubeAdapter
    from bilibili import BilibiliAdapter
    from weixin import WeixinAdapter

ADAPTERS = [
    YouTubeAdapter,
    BilibiliAdapter,
    WeixinAdapter,
]

def get_adapter_for_url(url: str) -> BaseAdapter:
    """Find and instantiate the matching adapter for a URL."""
    for adapter_cls in ADAPTERS:
        if adapter_cls.can_handle(url):
            return adapter_cls()
    raise ValueError(f"No adapter registered for URL: {url}")
