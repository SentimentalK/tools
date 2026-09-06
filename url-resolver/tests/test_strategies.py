"""
Unit tests for GenericStaticStrategy and WeixinPreviewStrategy.
Verifies outcome statuses, diagnostics, fields_resolved, and graceful fallbacks.
"""

import unittest
from unittest.mock import MagicMock
from url_resolver.fetch.base import FetchRequest, FetchResult, WebFetcher
from url_resolver.models import ContentMetadataV1, METADATA_OBSERVATION_FIELDS, ResolutionOutcome
from url_resolver.strategies.generic_static import GenericStaticStrategy
from url_resolver.strategies.weixin_preview import WeixinPreviewStrategy


class MockWebFetcher(WebFetcher):
    def __init__(self, result: FetchResult):
        self.result = result

    def fetch(self, request: FetchRequest) -> FetchResult:
        return self.result


class TestStrategies(unittest.TestCase):
    def test_generic_static_success(self):
        html = """
        <html>
        <head>
            <meta property="og:title" content="Resolved Video" />
            <meta property="og:description" content="A description" />
            <meta property="og:image" content="https://img.com/pic.jpg" />
        </head>
        </html>
        """
        fetch_res = FetchResult(
            requested_url="https://youtube.com/watch?v=123",
            final_url="https://youtube.com/watch?v=123",
            http_status=200,
            content_type="text/html",
            headers={},
            body=html,
            latency_ms=150,
            blocked=False,
        )
        strategy = GenericStaticStrategy(fetcher=MockWebFetcher(fetch_res))
        outcome = strategy.resolve(
            url="https://youtube.com/watch?v=123",
            source_type="youtube",
            source_id="123",
        )

        self.assertEqual(outcome.status, "resolved")
        self.assertIn("title", outcome.fields_resolved)
        self.assertIn("description", outcome.fields_resolved)
        self.assertIn("thumbnail_url", outcome.fields_resolved)
        # Verify identity fields are NOT in fields_resolved
        for ident in ("source_url", "canonical_url", "source_type", "source_id"):
            self.assertNotIn(ident, outcome.fields_resolved)

        self.assertEqual(outcome.metadata.title, "Resolved Video")
        self.assertEqual(outcome.diagnostics.strategy, "generic_static")
        self.assertEqual(outcome.diagnostics.fetch_status, "ok")
        self.assertIsNone(outcome.diagnostics.code)

    def test_generic_static_blocked_412(self):
        fetch_res = FetchResult(
            requested_url="https://bilibili.com/video/BV123",
            final_url="https://bilibili.com/video/BV123",
            http_status=412,
            content_type="text/html",
            headers={},
            body="<html>Precondition Failed</html>",
            latency_ms=80,
            blocked=True,
            block_reason="HTTP 412 Precondition Failed",
        )
        strategy = GenericStaticStrategy(fetcher=MockWebFetcher(fetch_res))
        outcome = strategy.resolve(
            url="https://bilibili.com/video/BV123",
            source_type="bilibili",
            source_id="BV123",
        )

        self.assertEqual(outcome.status, "unavailable")
        self.assertEqual(outcome.fields_resolved, [])
        self.assertEqual(outcome.metadata.source_id, "BV123")
        self.assertEqual(outcome.diagnostics.strategy, "generic_static")
        self.assertEqual(outcome.diagnostics.fetch_status, "blocked")
        self.assertEqual(outcome.diagnostics.http_status, 412)
        self.assertEqual(outcome.diagnostics.code, "ACCESS_BLOCKED")

    def test_generic_static_timeout(self):
        fetch_res = FetchResult(
            requested_url="https://example.com",
            final_url="https://example.com",
            http_status=0,
            content_type=None,
            headers={},
            body="",
            latency_ms=15000,
            blocked=True,
            block_reason="TIMEOUT: Request timed out",
        )
        strategy = GenericStaticStrategy(fetcher=MockWebFetcher(fetch_res))
        outcome = strategy.resolve(url="https://example.com", source_type="web")

        self.assertEqual(outcome.status, "unavailable")
        self.assertEqual(outcome.fields_resolved, [])
        self.assertEqual(outcome.diagnostics.fetch_status, "timeout")
        self.assertEqual(outcome.diagnostics.code, "TIMEOUT")

    def test_weixin_preview_success(self):
        api_json = """
        {
            "errCode": 0,
            "data": {
                "feedInfo": {
                    "description": "鹦鹉测试视频",
                    "coverUrl": "https://finder.video.qq.com/thumb.jpg",
                    "createtime": 1725494400
                },
                "authorInfo": {
                    "nickname": "测试作者"
                },
                "sceneInfo": {
                    "likeCount": "1.1万",
                    "commentCount": "880"
                }
            }
        }
        """
        api_res = FetchResult(
            requested_url="https://channels.weixin.qq.com/api",
            final_url="https://channels.weixin.qq.com/api",
            http_status=200,
            content_type="application/json",
            headers={},
            body=api_json,
            latency_ms=200,
        )
        strategy = WeixinPreviewStrategy(api_fetcher=MockWebFetcher(api_res))
        outcome = strategy.resolve(
            url="https://weixin.qq.com/sph/AF123",
            source_type="weixin",
            source_id="AF123",
        )

        self.assertEqual(outcome.status, "resolved")
        self.assertEqual(outcome.metadata.title, "鹦鹉测试视频")
        self.assertEqual(outcome.metadata.creator, "测试作者")
        self.assertEqual(outcome.metadata.like_count, "1.1万")
        self.assertIn("title", outcome.fields_resolved)
        self.assertIn("creator", outcome.fields_resolved)
        self.assertEqual(outcome.diagnostics.strategy, "weixin_preview")

    def test_weixin_preview_failure_fallback_to_generic(self):
        # API returns error 500
        api_res = FetchResult(
            requested_url="https://channels.weixin.qq.com/api",
            final_url="https://channels.weixin.qq.com/api",
            http_status=500,
            content_type="text/plain",
            headers={},
            body="Server Error",
            latency_ms=100,
            blocked=True,
        )
        # Fallback returns generic HTML
        fallback_html = "<html><head><title>Fallback Page Title</title></head></html>"
        fallback_res = FetchResult(
            requested_url="https://weixin.qq.com/sph/AF123",
            final_url="https://weixin.qq.com/sph/AF123",
            http_status=200,
            content_type="text/html",
            headers={},
            body=fallback_html,
            latency_ms=300,
        )
        generic_strat = GenericStaticStrategy(fetcher=MockWebFetcher(fallback_res))
        strategy = WeixinPreviewStrategy(
            api_fetcher=MockWebFetcher(api_res),
            fallback_strategy=generic_strat,
        )
        outcome = strategy.resolve(
            url="https://weixin.qq.com/sph/AF123",
            source_type="weixin",
            source_id="AF123",
        )

        self.assertEqual(outcome.status, "resolved")
        self.assertEqual(outcome.metadata.title, "Fallback Page Title")
        self.assertEqual(outcome.diagnostics.strategy, "generic_static")


if __name__ == "__main__":
    unittest.main()
