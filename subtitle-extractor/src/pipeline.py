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
    from .models import ResolvedContent
except (ImportError, ValueError):
    from adapters import get_adapter_for_url
    from asr import download_media_for_asr, transcribe_media_file
    from markdown import export_markdown, sanitize_filename
    from models import ResolvedContent


class Pipeline:
    """Ingestion pipeline for processing video URLs into structured Markdown."""

    def __init__(self, output_dir: Optional[str] = None, enable_asr_fallback: bool = False):
        self.output_dir = output_dir or os.getcwd()
        self.enable_asr_fallback = enable_asr_fallback

    def process_url(self, url: str) -> Tuple[str, ResolvedContent]:
        """
        Process a single URL:
        1. Select adapter
        2. Resolve metadata and native subtitles
        3. Optional ASR fallback for supported platforms
        4. Export to Markdown
        """
        adapter = get_adapter_for_url(url)
        print(f"▶ 识别平台: {adapter.__class__.__name__} ({url})")

        with tempfile.TemporaryDirectory(prefix="ingest_") as tmp_dir:
            resolved = adapter.resolve(url, tmp_dir=tmp_dir)

            # Optional ASR fallback: only if enabled and supported (YouTube/Bilibili), never for Weixin
            if (
                self.enable_asr_fallback
                and resolved.metadata.source_type in ("youtube", "bilibili")
                and resolved.transcript_status == "unavailable"
            ):
                print("▶ 未检测到原生字幕，尝试启动 ASR Fallback 流程...")
                prefix = f"asr_{resolved.metadata.source_id or 'media'}"
                media_file = download_media_for_asr(url, tmp_dir, prefix)
                if media_file and os.path.exists(media_file):
                    try:
                        transcript = transcribe_media_file(media_file)
                        if transcript:
                            resolved.transcript = transcript
                            resolved.transcript_status = "available"
                            resolved.transcript_method = "whisper-asr"
                            print("✔ ASR 语音识别成功！")
                    except Exception as e:
                        print(f"⚠ ASR 转录失败: {e}")

        # Export to Markdown
        clean_title = sanitize_filename(resolved.metadata.title or "Untitled")
        out_filename = f"{clean_title}.md"
        out_path = os.path.join(self.output_dir, out_filename)
        
        md_text = export_markdown(resolved)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_text)

        print(f"✨ 导出 Markdown 成功: {out_path}")
        return out_path, resolved
