# Subtitle Extractor & URL Content Ingestion Scaffold

支持 YouTube、B站 (Bilibili) 与 **微信视频号 (WeChat Channels SPH)** 的音视频内容抓取、字幕提取、本地 ASR 语音识别与标准化 Markdown/YAML 结构化导出。

---

## 1. 架构设计

系统采用模块化 Ingestion Scaffold 设计，严格分离“平台元数据解析 (Platform Resolving)”与“媒体流/内容增强 (Content Enrichment)”：

```text
URL
 ↓
Platform Detection (get_adapter_for_url)
 ↓
Platform Adapter (YouTube / Bilibili / Weixin [纯匿名元数据])
 ↓
ResolvedContent (ContentMetadata + Transcript + Status)
 ↓
Optional Media Providers & Enrichers (开启 --enable-asr 时按需触发)
 ├─ YouTube/B站: yt-dlp 媒体下载 + Faster-Whisper ASR
 └─ 微信视频号: WeixinMediaProvider (复用本地 Chrome 元宝会话) + Faster-Whisper ASR
 ↓
Markdown Exporter (YAML Front Matter + Body)
```

### 核心目录结构 (`src/`)

```text
src/
├── cli.py               # 命令行统一入口 (支持 --enable-asr, --browser, --profile)
├── pipeline.py          # 核心流程调度管线 (适配器解析、媒体获取与优雅降级)
├── models.py            # 统一数据模型 (ContentMetadata, ResolvedContent)
├── markdown.py          # YAML Front Matter 生成与 Markdown 导出
│
├── adapters/            # 平台解析适配器 (纯匿名元数据抓取)
│   ├── base.py          # BaseAdapter 抽象接口
│   ├── youtube.py       # YouTube 适配器 (基于 yt-dlp)
│   ├── bilibili.py      # B站适配器 (基于 yt-dlp)
│   └── weixin.py        # 微信视频号适配器 (基于轻量匿名预览 API)
│
├── media/               # 媒体获取提供者 (隔离认证与媒体流下载)
│   ├── base.py          # BaseMediaProvider 与类型化异常
│   └── weixin.py        # 微信媒体获取者 (安全过滤本地 Chrome 元宝 Cookie)
│
├── ytdlp.py             # yt-dlp 动态定位、元数据抓取与字幕解析
├── asr.py               # 离线 Faster-Whisper ASR 模块 (解耦按需调用)
└── unified_subtitles.py # 兼容旧版调用的统一入口
```

---

## 2. 平台支持与行为说明

| 平台 | URL 示例 | 元数据获取 | 字幕/文稿机制 | ASR 行为 (`--enable-asr`) |
|---|---|---|---|---|
| **YouTube** | `https://www.youtube.com/watch?v=...`<br>`https://youtu.be/...` | yt-dlp (`-J`) | 优先官方字幕，无官方字幕则尝试自动字幕 | yt-dlp 音频下载 + Whisper 转录 |
| **Bilibili** | `https://www.bilibili.com/video/BV...`<br>`https://b23.tv/...` | yt-dlp (`-J`) | 优先官方字幕/AI字幕 | yt-dlp 音频下载 + Whisper 转录 |
| **微信视频号** | `https://weixin.qq.com/sph/...`<br>`https://channels.weixin.qq.com/...` | 腾讯内部预览接口 (匿名 `shortUri`) | 默认不含外挂字幕 (`unavailable`)；开启 ASR 时转录语音 | **复用本地 Chrome 元宝会话**，0 额外浏览器进程，下载 H.264 流并转录 |

> [!NOTE]
> **关键设计语义**：
> 1. `no native transcript != extraction failure`：在默认模式下，微信视频号无需登录即可在 <200ms 内导出包含作者、文案、封面及互动量的完整 Markdown。
> 2. **零手动凭证传输**：用户只要在日常 Chrome 浏览器中登录过腾讯元宝（`yuanbao.tencent.com`），开启 `--enable-asr` 后工具会自动按域名严格过滤会话 Cookie 并下载真实媒体流，完全无需手动复制 Cookie，无需开启桌面微信，无需 MITM 抓包。
> 3. **会话过期优雅降级**：若元宝会话失效，系统记录警告并平滑回退至元数据文档，不会导致流水线崩溃。

---

## 3. 安装与使用

### 安装依赖

```bash
pip install -r requirements.txt
```

### 命令行使用 (`cli.py`)

```bash
# 1. 抓取单个链接 (微信视频号默认元数据模式，极速且无需登录)
python src/cli.py "https://weixin.qq.com/sph/AF17JEGHVd"

# 2. 微信视频号启用 ASR 语音识别 (自动读取本机 Chrome 登录态，转录完成后立即清理临时视频)
python src/cli.py "https://weixin.qq.com/sph/AF17JEGHVd" --enable-asr

# 3. 指定输出目录
python src/cli.py "https://www.youtube.com/watch?v=_QdPW8JrYzQ" -o ./transcripts

# 4. 批量抓取多个链接
python src/cli.py <url_1> <url_2> <url_3> -o ./output
```

### 兼容模式 (`unified_subtitles.py`)

现有老脚本调用方式保持完全向后兼容：

```bash
python src/unified_subtitles.py <url>
```

---

## 4. 输出格式规范 (包含 ASR 转录示例)

```markdown
---
source_type: "weixin"
source_url: "https://weixin.qq.com/sph/AF17JEGHVd"
canonical_url: "https://weixin.qq.com/sph/AF17JEGHVd"
source_id: "AF17JEGHVd"
title: "鹦鹉:我也要这样婶儿的#看一遍笑一遍#萌宠#搞笑#抽象#万万没想到"
creator: "玩娱少女"
published_at: "2026-09-05"
duration_seconds: null
thumbnail_url: "https://finder.video.qq.com/..."
media_url: null
view_count: null
like_count: "9071"
comment_count: "732"
transcript_status: "available"
transcript_method: "whisper-asr"
captured_at: "2026-09-05T16:08:13-04:00"
platform_metadata:
  fav_count: "1.4万"
  forward_count: "1.9万"
  dynamic_export_id: "export/..."
  author_avatar: "https://wx.qlogo.cn/..."
---

# 鹦鹉:我也要这样婶儿的#看一遍笑一遍#萌宠#搞笑#抽象#万万没想到

> 视频链接: https://weixin.qq.com/sph/AF17JEGHVd

## Description

鹦鹉:我也要这样婶儿的#看一遍笑一遍#萌宠#搞笑#抽象#万万没想到

## Transcript

刷到网友家的音舞因为完理的量是不一样当场就不干了
```

---

## 5. 测试套件

运行包含域名过滤、凭证脱敏与类型化异常在内的完整离线测试：

```bash
python -m unittest discover -s tests -p "test_*.py"
```
