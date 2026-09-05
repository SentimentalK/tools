#!/usr/bin/env python3
"""
统一音视频字幕提取脚本 (Compatibility Entrypoint)

保留与原脚本完全一致的命令行使用方式，内部委托给模块化的 Pipeline 处理。
"""

import os
import sys

# Ensure src is in python path
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from pipeline import Pipeline


def process_video(url: str, output_dir: str = None) -> str:
    """兼容旧版函数签名的处理接口"""
    out_dir = output_dir or SRC_DIR
    pipeline = Pipeline(output_dir=out_dir, enable_asr_fallback=True)
    out_path, _ = pipeline.process_url(url)
    return out_path


if __name__ == "__main__":
    urls = sys.argv[1:] if len(sys.argv) > 1 else [
        "https://www.youtube.com/watch?v=jMjSVF14j30"
    ]
    for u in urls:
        process_video(u)
