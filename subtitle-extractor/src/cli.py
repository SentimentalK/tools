#!/usr/bin/env python3
"""
CLI entrypoint for subtitle-extractor & URL content ingestion scaffold.
"""

import argparse
import os
import sys

# Support running directly as a script
if __package__ is None or __package__ == "":
    SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)
    from pipeline import Pipeline
else:
    from .pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Extract metadata and transcripts from YouTube, Bilibili, and WeChat Channels (视频号)."
    )
    parser.add_argument("urls", nargs="+", help="One or more video URLs to ingest")
    parser.add_argument("-o", "--output-dir", default=".", help="Directory to save Markdown output files (default: .)")
    parser.add_argument(
        "--enable-asr",
        action="store_true",
        help="Enable Whisper ASR fallback when no native subtitles are found (supported platforms only)",
    )

    args = parser.parse_args()
    pipeline = Pipeline(output_dir=args.output_dir, enable_asr_fallback=args.enable_asr)

    success_count = 0
    for url in args.urls:
        print(f"\n==========================================")
        print(f"=== 开始处理: {url} ===")
        print(f"==========================================")
        try:
            out_path, resolved = pipeline.process_url(url)
            print(f"✔ 完成: {resolved.metadata.title} (状态: {resolved.transcript_status})")
            success_count += 1
        except Exception as e:
            print(f"❌ 处理失败 {url}: {e}", file=sys.stderr)

    print(f"\n全部处理完毕！成功处理 {success_count}/{len(args.urls)} 个链接。")
    if success_count < len(args.urls):
        sys.exit(1)


if __name__ == "__main__":
    main()
