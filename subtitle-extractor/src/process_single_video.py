#!/usr/bin/env python3
"""
提取单个 B站 视频的字幕并格式化输出为包含标题与整理文稿的 Markdown 文件，自动清理临时文件
"""

import os
import re
import json
import ssl
import subprocess
import urllib.request
import glob

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BVID = "BV1PT4y1n7JA"
YT_DLP_PATH = "/Library/Frameworks/Python.framework/Versions/3.12/bin/yt-dlp"
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    name = name.replace(' ', '_').replace('\t', '_')
    return name.strip('_')

def get_video_info(bvid):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    with urllib.request.urlopen(req, context=ctx) as resp:
        data = json.loads(resp.read().decode()).get('data', {})
    return data.get('title', bvid)

def srt_to_paragraphs(srt_path):
    if not os.path.exists(srt_path):
        return ""
    with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    blocks = content.strip().split('\n\n')
    text_lines = []
    prev_line = ""
    for block in blocks:
        block_lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(block_lines) >= 3:
            sub_text = ' '.join(block_lines[2:])
            if sub_text and sub_text != prev_line:
                text_lines.append(sub_text)
                prev_line = sub_text
        elif len(block_lines) == 2 and '-->' in block_lines[0]:
            sub_text = block_lines[1]
            if sub_text and sub_text != prev_line:
                text_lines.append(sub_text)
                prev_line = sub_text

    # 合并为通顺的大段落
    paragraphs = []
    chunk_size = 12
    for i in range(0, len(text_lines), chunk_size):
        paragraph = "".join(text_lines[i:i+chunk_size])
        paragraphs.append(paragraph)
        
    return "\n\n".join(paragraphs)

def main():
    title = get_video_info(BVID)
    clean_title = sanitize_filename(title)
    print(f"正在提取视频: {title} ({BVID})...")
    
    tmp_template = os.path.join(WORKSPACE_DIR, f"tmp_{clean_title}.%(ext)s")
    url = f"https://www.bilibili.com/video/{BVID}"
    
    cmd = [
        YT_DLP_PATH,
        "--cookies-from-browser", "chrome",
        "--skip-download",
        "--write-sub",
        "--write-auto-sub",
        "--sub-lang", "ai-zh,zh-Hans,zh-CN,zh,all",
        "-o", tmp_template,
        url
    ]
    
    subprocess.run(cmd, capture_output=True, text=True)
    
    # 查找提取出的 srt 文件
    found_srt = None
    for f in glob.glob(os.path.join(WORKSPACE_DIR, f"tmp_{clean_title}*.srt")):
        found_srt = f
        break
        
    if not found_srt:
        print("未检测到 SRT 字幕文件！")
        return
        
    paragraphs = srt_to_paragraphs(found_srt)
    
    # 生成 Markdown 文档
    output_filename = os.path.join(WORKSPACE_DIR, f"{clean_title}.md")
    md_content = f"# {title}\n\n> 视频链接: {url}\n\n---\n\n{paragraphs}\n"
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    print(f"处理完成！最终文档已保存至: {output_filename}")
    
    # 清理临时 srt 和 xml 文件
    for tmp_file in glob.glob(os.path.join(WORKSPACE_DIR, f"tmp_{clean_title}*")):
        try:
            os.remove(tmp_file)
        except Exception:
            pass
    print("清理所有临时字幕与弹幕文件完成。")

if __name__ == "__main__":
    main()
