#!/usr/bin/env python3
"""
将 28 集语法课程字幕整理合并为一个完整的文档，并清理无用 .srt 和 .xml 文件
"""

import os
import glob
import re

SUBTITLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subtitles")
OUTPUT_MASTER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "半个月搭建你的英语语法体系_全集字幕汇总.md")

def cleanup_files():
    """删除所有的 .srt, .xml 等中转临时字幕与弹幕文件"""
    extensions = ['*.srt', '*.xml', '*.vtt']
    deleted_count = 0
    for ext in extensions:
        for f in glob.glob(os.path.join(SUBTITLES_DIR, ext)):
            try:
                os.remove(f)
                deleted_count += 1
            except Exception as e:
                print(f"删除失败 {f}: {e}")
    print(f"已清理 {deleted_count} 个临时 .srt 和 .xml/.vtt 文件。")

def format_text_into_paragraphs(lines):
    """将逐行的短句字幕合并为连续通顺的段落"""
    clean_lines = []
    prev_line = ""
    for line in lines:
        line = line.strip()
        if not line or line == prev_line:
            continue
        clean_lines.append(line)
        prev_line = line
        
    # 每 10-15 句合并为自然段落，方便阅读
    paragraphs = []
    chunk_size = 12
    for i in range(0, len(clean_lines), chunk_size):
        paragraph = "".join(clean_lines[i:i+chunk_size])
        paragraphs.append(paragraph)
        
    return "\n\n".join(paragraphs)

def merge_all_subtitles():
    # 查找所有单独的 .txt 文件，按数字序号排序
    txt_files = sorted(glob.glob(os.path.join(SUBTITLES_DIR, "*.txt")))
    
    # 过滤掉合集文件本身（如果有）
    txt_files = [f for f in txt_files if not f.endswith("complete_course_subtitles.txt")]
    
    doc_sections = [
        "# 【半个月，搭建你的英语语法体系】全集字幕合集文稿\n",
        "> 本文档合并自 28 集语法课程字幕，包含所有课程标题与精简整合后的文稿内容。\n",
        "---\n"
    ]
    
    for idx, filepath in enumerate(txt_files, 1):
        filename = os.path.basename(filepath)
        # 从文件名提取干净标题
        clean_title = re.sub(r'^\d+_', '', filename).replace('.txt', '').replace('_', ' ')
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        paragraph_text = format_text_into_paragraphs(lines)
        
        section_md = f"## 第 {idx:02d} 课：{clean_title}\n\n{paragraph_text}\n\n---\n"
        doc_sections.append(section_md)
        
    master_content = "\n".join(doc_sections)
    
    with open(OUTPUT_MASTER_FILE, 'w', encoding='utf-8') as f:
        f.write(master_content)
        
    print(f"已成功将全部 28 集合并为单个主文档: {OUTPUT_MASTER_FILE}")
    
    # 将 subtitles 目录下的分集 txt 文件也清理干净，只留主文档
    for filepath in txt_files:
        try:
            os.remove(filepath)
        except Exception:
            pass
    print("已删除分集 .txt 文件，仅保留最终合并文档。")

if __name__ == "__main__":
    cleanup_files()
    merge_all_subtitles()
