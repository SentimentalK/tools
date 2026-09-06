"""
End-to-end integration tests for resolve_url entrypoint.
"""

import unittest
from unittest.mock import patch, MagicMock
from url_resolver import resolve_url, ResolverValidationError, ResolutionOutcome


class TestResolveUrlEntrypoint(unittest.TestCase):
    def test_resolve_generic_web(self):
        html = """
        <html>
        <head>
            <meta property="og:title" content="Tech News Today" />
            <meta property="og:description" content="Daily tech summary" />
        </head>
        <body>Valid article content body here</body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.url = "https://example.com/article"
        mock_resp.html_content = html
        mock_resp.headers = {"content-type": "text/html"}

        with patch("scrapling.fetchers.Fetcher.get", return_value=mock_resp):
            outcome = resolve_url("https://example.com/article")
            self.assertEqual(outcome.status, "resolved")
            self.assertEqual(outcome.metadata.title, "Tech News Today")
            self.assertEqual(outcome.metadata.description, "Daily tech summary")
            self.assertEqual(outcome.metadata.source_type, "web")
            self.assertIn("title", outcome.fields_resolved)
            self.assertIn("description", outcome.fields_resolved)

    def test_resolve_youtube_generic(self):
        html = """
        <html>
        <head>
            <meta property="og:title" content="Rick Astley Video" />
            <meta property="og:image" content="https://img.youtube.com/thumb.jpg" />
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "VideoObject",
                "name": "Rick Astley Video",
                "duration": "PT213S",
                "author": {"name": "RickAstleyVEVO"}
            }
            </script>
        </head>
        <body>YouTube player webpage content here</body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        mock_resp.html_content = html
        mock_resp.headers = {}

        with patch("scrapling.fetchers.Fetcher.get", return_value=mock_resp):
            outcome = resolve_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            self.assertEqual(outcome.status, "resolved")
            self.assertEqual(outcome.metadata.source_type, "youtube")
            self.assertEqual(outcome.metadata.source_id, "dQw4w9WgXcQ")
            self.assertEqual(outcome.metadata.title, "Rick Astley Video")
            self.assertEqual(outcome.metadata.creator, "RickAstleyVEVO")
            self.assertEqual(outcome.metadata.duration_seconds, 213)

    def test_resolve_malformed_url_raises_exception(self):
        with self.assertRaises(ResolverValidationError):
            resolve_url("htp:/not-a-url")


if __name__ == "__main__":
    unittest.main()
