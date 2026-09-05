"""
Unit tests for the two public capabilities:
1. resolve_url(url) -> ContentMetadata
2. extract_url(url) -> ResolvedContent
Strict boundary verification that resolve_url never touches cookies, media, subtitles, ASR, or temp dirs.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.api import extract_url, resolve_url
from src.models import (
    ContentMetadata,
    ResolveError,
    ResolvedContent,
    TranscriptResult,
    UnsupportedURLError,
)


class TestTwoCapabilities(unittest.TestCase):
    def test_resolve_url_strict_boundary(self):
        """
        Verify resolve_url() is lightweight/read-only:
        MUST NOT call subtitle download, media providers, browser-cookie extraction,
        model manager, ASR, or .tmp/ directory creation.
        """
        fake_meta = ContentMetadata(
            source_type="weixin",
            source_url="https://weixin.qq.com/sph/AF17JEGHVd",
            title="Fake Video",
            creator="Author",
        )

        with patch("src.adapters.weixin.WeixinAdapter.resolve_metadata", return_value=fake_meta) as mock_resolve_meta, \
             patch("src.media.weixin.extract_cookies_from_browser") as mock_extract_cookies, \
             patch("src.media.weixin.WeixinMediaProvider.acquire") as mock_acquire_media, \
             patch("src.ytdlp.download_subtitles") as mock_download_subs, \
             patch("src.asr.download_media_for_asr") as mock_download_media, \
             patch("src.asr.transcribe_media_file") as mock_asr, \
             patch("src.model_manager.ensure_all_asr_models") as mock_ensure_models, \
             patch("tempfile.TemporaryDirectory") as mock_tmp_dir:

            meta = resolve_url("https://weixin.qq.com/sph/AF17JEGHVd")

            # 1. Must return pure ContentMetadata (not ResolvedContent)
            self.assertIsInstance(meta, ContentMetadata)
            self.assertNotIsInstance(meta, ResolvedContent)
            self.assertEqual(meta.title, "Fake Video")

            # 2. Strict boundary guarantees
            mock_resolve_meta.assert_called_once()
            mock_extract_cookies.assert_not_called()
            mock_acquire_media.assert_not_called()
            mock_download_subs.assert_not_called()
            mock_download_media.assert_not_called()
            mock_asr.assert_not_called()
            mock_ensure_models.assert_not_called()
            mock_tmp_dir.assert_not_called()

    def test_resolve_url_failure_raises_typed_resolve_error(self):
        """Verify resolve_url() raises ResolveError rather than returning fabricated fallback metadata."""
        # Empty/invalid SPH
        with self.assertRaises(ResolveError):
            resolve_url("https://weixin.qq.com/sph/")

    def test_resolve_unsupported_url_raises_unsupported_url_error(self):
        """Verify resolve_url() on unknown domain raises UnsupportedURLError (subclass of ResolveError)."""
        with self.assertRaises(UnsupportedURLError) as ctx:
            resolve_url("https://vimeo.com/12345678")

        self.assertIsInstance(ctx.exception, ResolveError)
        self.assertIsInstance(ctx.exception, ValueError)

    def test_extract_url_is_completely_self_contained(self):
        """
        Verify extract_url() works directly without prior resolve_url() call,
        independently resolving metadata and returning ResolvedContent.
        """
        fake_meta = ContentMetadata(
            source_type="youtube",
            source_url="https://www.youtube.com/watch?v=123",
            title="YT Video",
        )
        fake_transcript = TranscriptResult(text="Hello world subtitles", method="subtitles")

        with patch("src.adapters.youtube.YouTubeAdapter.resolve_metadata", return_value=fake_meta) as mock_meta, \
             patch("src.adapters.youtube.YouTubeAdapter.try_get_native_transcript", return_value=fake_transcript) as mock_native:

            result = extract_url("https://www.youtube.com/watch?v=123")

            self.assertIsInstance(result, ResolvedContent)
            self.assertEqual(result.metadata.title, "YT Video")
            self.assertEqual(result.transcript, "Hello world subtitles")
            self.assertEqual(result.transcript_status, "available")
            self.assertEqual(result.transcript_method, "subtitles")

            mock_meta.assert_called_once()
            mock_native.assert_called_once()

    def test_extract_url_falls_back_to_asr_when_native_unavailable(self):
        """
        Verify extract_url() falls back to media acquisition and FireRedASR2
        when native subtitles are not available.
        """
        fake_meta = ContentMetadata(
            source_type="weixin",
            source_url="https://weixin.qq.com/sph/AF17JEGHVd",
            title="SPH Video",
        )

        with patch("src.adapters.weixin.WeixinAdapter.resolve_metadata", return_value=fake_meta), \
             patch("src.adapters.weixin.WeixinAdapter.try_get_native_transcript", return_value=None), \
             patch("src.media.weixin.WeixinMediaProvider.acquire", return_value="/tmp/mock_media.mp4"), \
             patch("src.asr.transcribe_media_file", return_value="语音识别转录文本") as mock_transcribe, \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):

            result = extract_url("https://weixin.qq.com/sph/AF17JEGHVd")

            self.assertIsInstance(result, ResolvedContent)
            self.assertEqual(result.transcript, "语音识别转录文本")
            self.assertEqual(result.transcript_status, "available")
            self.assertEqual(result.transcript_method, "firered-asr2-aed")
            mock_transcribe.assert_called_once_with("/tmp/mock_media.mp4")


if __name__ == "__main__":
    unittest.main()
