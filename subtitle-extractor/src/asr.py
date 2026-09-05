"""
Whisper ASR transcription module.
Decoupled from platform adapters; invoked only when explicitly requested.
"""

import glob
import os
import subprocess
from typing import Optional
try:
    from .ytdlp import build_base_ytdlp_cmd
except (ImportError, ValueError):
    from ytdlp import build_base_ytdlp_cmd


def download_media_for_asr(url: str, output_dir: str, prefix: str) -> Optional[str]:
    """Download best audio for ASR fallback."""
    os.makedirs(output_dir, exist_ok=True)
    template = os.path.join(output_dir, f"{prefix}_media.%(ext)s")
    cmd = build_base_ytdlp_cmd(url, extra_args=["-f", "bestaudio/best", "-o", template])
    subprocess.run(cmd, capture_output=True, text=True)

    for f in glob.glob(os.path.join(output_dir, f"{prefix}_media.*")):
        return f
    return None


def transcribe_media_file(
    media_file: str,
    model_size: str = "tiny",
    language: str = "zh",
    chunk_size: int = 8,
) -> str:
    """Run faster-whisper ASR on an audio/video file."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("faster-whisper is not installed. Run `pip install faster-whisper` to enable ASR.")

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(media_file, vad_filter=True, language=language)

    text_lines = []
    for segment in segments:
        txt = segment.text.strip()
        if txt:
            text_lines.append(txt)

    paragraphs = []
    for i in range(0, len(text_lines), chunk_size):
        paragraph = "".join(text_lines[i : i + chunk_size])
        paragraphs.append(paragraph)

    return "\n\n".join(paragraphs)
