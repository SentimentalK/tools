"""
Core content ingestion pipeline:
URL -> Platform Detection -> Platform Adapter -> Optional ASR -> Markdown Exporter
"""

import os
import tempfile
from typing import Optional, Tuple

try:
    from .adapters import get_adapter_for_url
    from .asr import download_media_for_asr, transcribe_media_file
    from .markdown import export_markdown, sanitize_filename
    from .media import (
        MediaAuthError,
        MediaDownloadError,
        MediaProviderError,
        MediaResolveError,
        get_media_provider,
    )
    from .models import ResolvedContent
except (ImportError, ValueError):
    from adapters import get_adapter_for_url
    from asr import download_media_for_asr, transcribe_media_file
    from markdown import export_markdown, sanitize_filename
    from media import (
        MediaAuthError,
        MediaDownloadError,
        MediaProviderError,
        MediaResolveError,
        get_media_provider,
    )
    from models import ResolvedContent


class Pipeline:
    """Ingestion pipeline for processing video URLs into structured Markdown."""

    def __init__(
        self,
        output_dir: Optional[str] = None,
        enable_asr_fallback: bool = False,
        browser_name: str = "chrome",
        profile_name: str = "Default",
    ):
        self.output_dir = output_dir or os.getcwd()
        self.enable_asr_fallback = enable_asr_fallback
        self.browser_name = browser_name
        self.profile_name = profile_name

    def process_url(self, url: str) -> Tuple[str, ResolvedContent]:
        """
        Process a single URL:
        1. Select adapter
        2. Resolve metadata and native subtitles (purely anonymous)
        3. Optional ASR fallback using platform media provider if enabled
        4. Export to Markdown
        """
        adapter = get_adapter_for_url(url)
        print(f"▶ 识别平台: {adapter.__class__.__name__} ({url})")

        with tempfile.TemporaryDirectory(prefix="ingest_") as tmp_dir:
            # Step 1: Adapter resolves metadata and native subtitles
            resolved = adapter.resolve(url, tmp_dir=tmp_dir)

            # Step 2: Optional ASR fallback (only when enabled and native transcript is unavailable)
            if self.enable_asr_fallback and resolved.transcript_status == "unavailable":
                media_file = None
                prefix = f"asr_{resolved.metadata.source_id or 'media'}"

                if resolved.metadata.source_type == "weixin":
                    print("▶ 微信视频号未包含外挂字幕，尝试通过本地浏览器会话获取媒体流...")
                    try:
                        provider = get_media_provider(
                            "weixin",
                            browser_name=self.browser_name,
                            profile_name=self.profile_name,
                        )
                        if provider:
                            media_file = provider.acquire(url, tmp_dir, prefix)
                    except MediaAuthError as e:
                        print(f"⚠ 微信媒体认证失败 (跳过 ASR): {e}")
                    except MediaResolveError as e:
                        print(f"⚠ 微信媒体解析失败 (跳过 ASR): {e}")
                    except MediaDownloadError as e:
                        print(f"⚠ 微信媒体下载失败 (跳过 ASR): {e}")
                    except MediaProviderError as e:
                        print(f"⚠ 微信媒体获取失败 (跳过 ASR): {e}")
                    except Exception as e:
                        print(f"⚠ 媒体获取发生异常 (跳过 ASR): {e}")

                elif resolved.metadata.source_type in ("youtube", "bilibili"):
                    print("▶ 未检测到原生字幕，尝试启动 yt-dlp 音频下载...")
                    try:
                        media_file = download_media_for_asr(url, tmp_dir, prefix)
                    except Exception as e:
                        print(f"⚠ 媒体下载失败 (跳过 ASR): {e}")

                # If media was acquired, run speech recognition
                if media_file and os.path.exists(media_file):
                    try:
                        print("▶ 运行 Faster-Whisper ASR 语音识别...")
                        transcript = transcribe_media_file(media_file)
                        if transcript:
                            resolved.transcript = transcript
                            resolved.transcript_status = "available"
                            resolved.transcript_method = "whisper-asr"
                            print("✔ ASR 语音识别成功！")
                    except Exception as e:
                        print(f"⚠ ASR 转录失败: {e}")
                    finally:
                        if os.path.exists(media_file):
                            try:
                                os.remove(media_file)
                            except Exception:
                                pass

        # Step 3: Export to Markdown
        clean_title = sanitize_filename(resolved.metadata.title or "Untitled")
        out_filename = f"{clean_title}.md"
        out_path = os.path.join(self.output_dir, out_filename)

        md_text = export_markdown(resolved)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_text)

        print(f"✨ 导出 Markdown 成功: {out_path}")
        return out_path, resolved
