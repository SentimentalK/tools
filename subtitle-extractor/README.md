# Subtitle Extractor & URL Content Ingestion Scaffold

支持 YouTube、B站 (Bilibili) 与 **微信视频号 (WeChat Channels SPH)** 的音视频内容抓取、字幕提取与标准化 Markdown/YAML 结构化导出。

---

## 1. 架构设计

系统采用模块化 Ingestion Scaffold 设计，分离“平台解析 (Platform Resolving)”与“内容增强 (Content Enrichment)”：

```text
URL
 ↓
Platform Detection (get_adapter_for_url)
 ↓
Platform Adapter (YouTube / Bilibili / Weixin)
 ↓
ResolvedContent (ContentMetadata + Transcript + Status)
 ↓
Optional Enrichers (ASR Fallback for supported platforms)
 ↓
Markdown Exporter (YAML Front Matter + Body)
```

### 核心目录结构 (`src/`)

```text
src/
├── cli.py               # 命令行统一入口
├── pipeline.py          # 核心流程调度管线
├── models.py            # 统一数据模型 (ContentMetadata, ResolvedContent)
├── markdown.py          # YAML Front Matter 生成与 Markdown 导出
│
├── adapters/            # 平台解析适配器
│   ├── base.py          # BaseAdapter 抽象接口
│   ├── youtube.py       # YouTube 适配器 (基于 yt-dlp)
│   ├── bilibili.py      # B站适配器 (基于 yt-dlp)
│   └── weixin.py        # 微信视频号适配器 (基于轻量匿名预览 API)
│
├── ytdlp.py             # yt-dlp 动态定位、元数据抓取与字幕解析
├── asr.py               # 离线 Faster-Whisper ASR 模块 (解耦按需调用)
└── unified_subtitles.py # 兼容旧版调用的统一入口
```

---

## 2. 平台支持与行为说明

| 平台 | URL 示例 | 元数据获取 | 字幕/文稿机制 | ASR 行为 |
|---|---|---|---|---|
| **YouTube** | `https://www.youtube.com/watch?v=...`<br>`https://youtu.be/...` | yt-dlp (`-J`) | 优先官方字幕，无官方字幕则尝试自动字幕 | 可选 fallback |
| **Bilibili** | `https://www.bilibili.com/video/BV...`<br>`https://b23.tv/...` | yt-dlp (`-J`) | 优先官方字幕/AI字幕 | 可选 fallback |
| **微信视频号** | `https://weixin.qq.com/sph/...`<br>`https://channels.weixin.qq.com/...` | 腾讯内部预览接口 (匿名 `shortUri`) | 视频号无独立外挂字幕，设为 `unavailable` | **不自动运行 ASR** |

> [!NOTE]
> **关键设计语义**：`no native transcript != extraction failure`。对于微信视频号等没有外挂字幕的平台，只要成功提取出标题、描述、作者、封面与互动数据，即视为合法成功的 Ingestion 结果，生成包含完整元数据的 Markdown。

---

## 3. 安装与使用

### 安装依赖

```bash
pip install -r requirements.txt
```

核心依赖：
- `yt-dlp` (音视频元数据与字幕抓取)
- `httpx` (HTTP 客户端请求)
- `faster-whisper` (可选，离线语音识别)

### 命令行使用 (`cli.py`)

```bash
# 抓取单个链接 (支持 YouTube / B站 / 微信视频号)
python src/cli.py "https://weixin.qq.com/sph/AF17JEGHVd"

# 指定输出目录
python src/cli.py "https://www.youtube.com/watch?v=_QdPW8JrYzQ" -o ./transcripts

# 启用 Whisper ASR 兜底 (仅针对支持媒体下载的平台如 YouTube/B站)
python src/cli.py "https://www.youtube.com/watch?v=..." --enable-asr

# 批量抓取多个链接
python src/cli.py <url_1> <url_2> <url_3> -o ./output
```

### 兼容模式 (`unified_subtitles.py`)

现有老脚本调用方式保持完全向后兼容：

```bash
python src/unified_subtitles.py <url>
```

---

## 4. 输出格式规范

生成的 Markdown 包含严格的 YAML Front Matter 头部与结构化章节：

```markdown
---
source_type: "weixin"
source_url: "https://weixin.qq.com/sph/AF17JEGHVd"
canonical_url: "https://weixin.qq.com/sph/AF17JEGHVd"
source_id: "AF17JEGHVd"
title: "鹦鹉:我也要这样婶儿的..."
creator: "玩娱少女"
published_at: "2026-09-05"
duration_seconds: null
thumbnail_url: "https://finder.video.qq.com/..."
media_url: null
view_count: null
like_count: "8999"
comment_count: "730"
transcript_status: "unavailable"
transcript_method: null
captured_at: "2026-09-05T15:29:52-04:00"
platform_metadata:
  fav_count: "1.4万"
  forward_count: "1.9万"
  dynamic_export_id: "export/..."
---

# Title

> 视频链接: https://...

## Description

...

## Transcript

Transcript unavailable.
```

---

## 5. 测试套件

运行离线单元测试（基于 `fixtures/`，无需网络或真实账号）：

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## 6. Phase 2 演进规划 (Roadmap)

1. **Media Acquisition Provider**：为微信等封闭平台预留插件式媒体流获取方案（如腾讯元宝 Cookie 会话桥接、桌面微信客户端代理抓包）。
2. **ASREnricher 语音检测分流**：根据音轨中是否有真实人声决定是否启动 Whisper，避免纯背景音乐短视频浪费算力。
3. **VisualTextEnricher 抽帧与 OCR**：针对无原生字幕但画面有大量关键代码、文字、黑板板书的短视频，通过采样关键帧结合 OCR 提取文字。
4. **TranscriptQuality Gating**：引入规则引擎，对字数过短、全为音乐标记（`[音乐]`）、重复幻觉等情况自动打标。
