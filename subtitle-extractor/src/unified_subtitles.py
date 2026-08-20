#!/usr/bin/env python3
"""
统一音视频字幕提取脚本：
1. 优先使用 yt-dlp 获取官方/自动生成字幕。
2. 若完全无字幕资源，自动降级 (Fallback): 使用 yt-dlp 下载最佳音频 + faster-whisper 自动语音识别生成文稿。
3. 动态获取全套元数据，生成包含 YAML Front Matter header 的唯一 Markdown (.md) 文件。
4. 清理所有临时音视频与字幕中间文件。
"""

import os
import sys
import re
import glob
import json
import datetime
import subprocess

# 解决 OpenMP 多库重叠初始化的警告/报错
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

YT_DLP_PATH = "/Library/Frameworks/Python.framework/Versions/3.12/bin/yt-dlp"
NODE_PATH = "/Users/sentimentalk/.nvm/versions/node/v22.22.0/bin"
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

env = os.environ.copy()
env["PATH"] = f"{NODE_PATH}:{env.get('PATH', '')}"

def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_')

def get_video_metadata(url):
    """获取完整的视频元数据 JSON"""
    cmd = [
        YT_DLP_PATH,
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--cookies-from-browser", "chrome",
        "--extractor-args", "youtube:player_client=web_creator,web",
        "-J",
        url
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    try:
        data = json.loads(res.stdout)
    except Exception:
        data = {}
        
    source_type = "youtube" if "youtube" in url.lower() or "youtu.be" in url.lower() else ("bilibili" if "bilibili" in url.lower() else "unknown")
    source_id = data.get("id") or ("" if source_type == "unknown" else url.split("v=")[-1].split("&")[0])
    title = data.get("title") or "Video_Transcript"
    creator = data.get("uploader") or data.get("channel") or data.get("uploader_id") or None
    
    pub_date = data.get("upload_date")
    if pub_date and len(pub_date) == 8:
        published_at = f"{pub_date[:4]}-{pub_date[4:6]}-{pub_date[6:8]}"
    else:
        published_at = None
        
    duration_seconds = data.get("duration")
    
    return {
        "source_type": source_type,
        "source_url": url,
        "source_id": source_id,
        "title": title,
        "creator": creator,
        "published_at": published_at,
        "duration_seconds": duration_seconds
    }

def try_download_ytdlp_subtitles(url, tmp_prefix):
    """尝试抓取官方或自动字幕"""
    tmp_template = os.path.join(WORKSPACE_DIR, f"{tmp_prefix}.%(ext)s")
    cmd = [
        YT_DLP_PATH,
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--cookies-from-browser", "chrome",
        "--extractor-args", "youtube:player_client=web_creator,web",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", "zh-Hans,zh-CN,zh,en",
        "--convert-subs", "srt",
        "-o", tmp_template,
        url
    ]
    subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    for ext in ['.zh-Hans.srt', '.zh-CN.srt', '.zh.srt', '.en.srt', '.srt', '.vtt']:
        found = glob.glob(os.path.join(WORKSPACE_DIR, f"{tmp_prefix}*{ext}"))
        if found:
            # 判断是官方字幕还是自动字幕
            method = "auto-subtitles" if ("auto" in found[0].lower() or "ai-" in found[0].lower()) else "subtitles"
            return found[0], method
    return None, None

def parse_srt_to_paragraphs(srt_path):
    with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    blocks = content.strip().split('\n\n')
    text_lines = []
    prev_line = ""
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) >= 3:
            sub_text = ' '.join(lines[2:])
            if sub_text and sub_text != prev_line:
                text_lines.append(sub_text)
                prev_line = sub_text
        elif len(lines) == 2 and '-->' in lines[0]:
            sub_text = lines[1]
            if sub_text and sub_text != prev_line:
                text_lines.append(sub_text)
                prev_line = sub_text

    paragraphs = []
    chunk_size = 10
    for i in range(0, len(text_lines), chunk_size):
        paragraph = "".join(text_lines[i:i+chunk_size])
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)

def transcribe_audio_fallback(url, tmp_prefix):
    print("▶ 检测到视频未包含在线字幕，启动 Fallback 流程：下载音频/视频 + ASR 转录...")
    media_template = os.path.join(WORKSPACE_DIR, f"{tmp_prefix}_media.%(ext)s")
    
    cmd = [
        YT_DLP_PATH,
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--cookies-from-browser", "chrome",
        "--extractor-args", "youtube:player_client=web_creator,web",
        "-f", "bestaudio/best",
        "-o", media_template,
        url
    ]
    subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    media_file = None
    for f in glob.glob(os.path.join(WORKSPACE_DIR, f"{tmp_prefix}_media.*")):
        media_file = f
        break
        
    if not media_file:
        print("错误：媒体数据下载失败！")
        return ""

    print(f"媒体文件已下载: {os.path.basename(media_file)}，正在运行 faster-whisper 语音识别...")
    
    from faster_whisper import WhisperModel
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, info = model.transcribe(media_file, vad_filter=True, language="zh")
    
    text_lines = []
    for segment in segments:
        txt = segment.text.strip()
        if txt:
            text_lines.append(txt)
            
    paragraphs = []
    chunk_size = 8
    for i in range(0, len(text_lines), chunk_size):
        paragraph = "".join(text_lines[i:i+chunk_size])
        paragraphs.append(paragraph)
        
    return "\n\n".join(paragraphs)

def format_yaml_val(val):
    if val is None:
        return "null"
    if isinstance(val, (int, float)):
        return str(val)
    # 字符串加引号保护
    val_str = str(val).replace('"', '\\"')
    return f'"{val_str}"'

def generate_yaml_front_matter(meta, transcript_method):
    local_now = datetime.datetime.now().astimezone().isoformat()
    yaml_lines = [
        "---",
        f"source_type: {meta['source_type']}",
        f"source_url: {meta['source_url']}",
        f"source_id: {meta['source_id']}",
        f"title: {format_yaml_val(meta['title'])}",
        f"creator: {format_yaml_val(meta['creator'])}",
        f"published_at: {format_yaml_val(meta['published_at'])}",
        f"captured_at: {local_now}",
        f"duration_seconds: {format_yaml_val(meta['duration_seconds'])}",
        f"transcript_method: {transcript_method}",
        "---"
    ]
    return "\n".join(yaml_lines)

def process_video(url):
    meta = get_video_metadata(url)
    raw_title = meta["title"]
    clean_title = sanitize_filename(raw_title)
    
    print(f"\n==========================================")
    print(f"=== 开始处理视频: {raw_title} ===")
    print(f"==========================================")
    
    tmp_prefix = f"tmp_{clean_title}"
    
    # 1. 尝试直接下载字幕
    sub_file, transcript_method = try_download_ytdlp_subtitles(url, tmp_prefix)
    
    if sub_file:
        print(f"✔ 成功从 {meta['source_type']} 抓取到字幕文件 ({transcript_method})！")
        paragraphs = parse_srt_to_paragraphs(sub_file)
    else:
        # 2. 降级方案：下载媒体 + faster-whisper
        transcript_method = "whisper-asr"
        paragraphs = transcribe_audio_fallback(url, tmp_prefix)

    if not paragraphs:
        print("未能提取到有效文字内容。")
        return None

    # 生成 YAML Header
    yaml_header = generate_yaml_front_matter(meta, transcript_method)
    
    # 保存为唯一的 Markdown 文件
    output_md = os.path.join(WORKSPACE_DIR, f"{clean_title}.md")
    md_content = f"{yaml_header}\n\n# {raw_title}\n\n> 视频链接: {url}\n\n---\n\n{paragraphs}\n"
    
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"\n✨ 处理完成！已导出带 Metadata 的唯一 Markdown 文档:\n{output_md}")
    
    # 清理所有临时文件
    for f in glob.glob(os.path.join(WORKSPACE_DIR, f"{tmp_prefix}*")):
        try:
            os.remove(f)
        except Exception:
            pass
    print("所有临时音频与字幕文件已清理完成。")
    return output_md

if __name__ == "__main__":
    urls = sys.argv[1:] if len(sys.argv) > 1 else [
        "https://www.youtube.com/watch?v=jMjSVF14j30"
    ]
    for u in urls:
        process_video(u)
