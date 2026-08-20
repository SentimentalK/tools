#!/usr/bin/env python3
"""
使用 yt-dlp 抓取 YouTube 视频字幕，并自动将文件名设置为真实的视频标题，带 YAML Metadata
"""

import os
import sys
import re
import glob
import json
import datetime
import subprocess

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
    title = data.get("title") or "YouTube_Video"
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

def format_yaml_val(val):
    if val is None:
        return "null"
    if isinstance(val, (int, float)):
        return str(val)
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

def srt_to_paragraphs(srt_path):
    if not os.path.exists(srt_path):
        return ""
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

def download_and_format_subtitles(url):
    meta = get_video_metadata(url)
    raw_title = meta["title"]
    clean_title = sanitize_filename(raw_title)
    print(f"正在获取视频标题及字幕: {raw_title} ...")
    
    tmp_prefix = f"tmp_sub_{clean_title}"
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
    
    found_srt = None
    transcript_method = "subtitles"
    for ext in ['.zh-Hans.srt', '.zh-CN.srt', '.zh.srt', '.en.srt', '.srt', '.vtt']:
        found = glob.glob(os.path.join(WORKSPACE_DIR, f"{tmp_prefix}*{ext}"))
        if found:
            found_srt = found[0]
            if "auto" in found_srt.lower() or "ai-" in found_srt.lower():
                transcript_method = "auto-subtitles"
            break
            
    if not found_srt:
        print("未检测到字幕文件。")
        return None
        
    paragraphs = srt_to_paragraphs(found_srt)
    
    yaml_header = generate_yaml_front_matter(meta, transcript_method)
    
    output_filename = os.path.join(WORKSPACE_DIR, f"{clean_title}.md")
    md_content = f"{yaml_header}\n\n# {raw_title}\n\n> 视频链接: {url}\n\n---\n\n{paragraphs}\n"
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    print(f"字幕提取与整理成功！文稿保存为: {output_filename}")
    
    for f in glob.glob(os.path.join(WORKSPACE_DIR, f"{tmp_prefix}*")):
        try:
            os.remove(f)
        except Exception:
            pass
            
    return output_filename

if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=jMjSVF14j30"
    download_and_format_subtitles(target_url)
