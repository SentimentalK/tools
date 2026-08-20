# Subtitle Extractor & Audio Transcriber (音视频字幕提取与转录工具)

支持 B站 (Bilibili)、YouTube 及本地音视频的字幕提取与 Whisper 离线转录。

## 脚本列表 (`src/`)

- `unified_subtitles.py`: 统一提取入口（优先官方/自动字幕，无字幕则自动 Fallback 到 Faster-Whisper 离线转写）。
- `process_youtube.py`: YouTube 视频字幕抓取并生成带 YAML 元数据的 Markdown。
- `download_subtitles.py`: B站 合集/分P 字幕批量下载。
- `process_single_video.py`: B站 单视频字幕抓取。
- `merge_subtitles.py`: 分P字幕合并与清洗整理。

## 依赖

```bash
pip install -r requirements.txt
```
