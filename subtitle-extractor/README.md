# Subtitle Extractor & URL Content Ingestion Scaffold

支持 YouTube、B站 (Bilibili) 与 **微信视频号 (WeChat Channels SPH)** 的音视频内容抓取、字幕提取、本地 2026 中文第一的 **FireRedASR2-AED** 离线语音识别与标准化 Markdown/YAML 结构化导出。

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
 ├─ YouTube/B站: yt-dlp 媒体下载 + FireRedASR2-AED ASR
 └─ 微信视频号: WeixinMediaProvider (复用本地 Chrome 元宝会话) + FireRedASR2-AED ASR
 ↓
Markdown Exporter (YAML Front Matter + Body)
```

### 运行时与项目目录结构

```text
subtitle-extractor/
├── .venv/                 # 宿主机本地 Python 虚拟环境 (由 setup.sh 创建)
├── .models/               # 本地自包含离线 ASR 模型 (Git 忽略)
│   ├── firered-asr2-aed-int8-2026-02-26/  # FireRedASR2-AED INT8 权重 (解压后约 1.2 GB)
│   └── silero_vad.onnx                    # Silero 语音活动检测模型
├── .tmp/                  # 项目本地运行时刮擦空间 (音频抽取、下载暂存，Git 忽略)
├── setup.sh               # 宿主机环境一键配置脚本
├── requirements.txt       # sherpa-onnx==1.13.7, yt-dlp, httpx, numpy
├── scripts/
│   └── prepare_asr_model.py # 显式预下载/校验模型辅助脚本
├── src/
│   ├── cli.py               # 命令行统一入口 (支持 --enable-asr, --browser, --profile)
│   ├── pipeline.py          # 核心流程调度管线 (适配器解析、媒体获取与优雅降级)
│   ├── models.py            # 统一数据模型 (ContentMetadata, ResolvedContent)
│   ├── model_manager.py     # 模型生命周期管理 (校验和验证、安全解压、原子替换)
│   ├── asr.py               # 离线 FireRedASR2-AED + Silero VAD 语音识别模块
│   ├── markdown.py          # YAML Front Matter 生成与 Markdown 导出
│   ├── adapters/            # 平台解析适配器 (纯匿名元数据抓取)
│   └── media/               # 媒体获取提供者 (隔离认证与媒体流下载)
└── tests/                   # 完整离线单元测试套件
```

---

## 2. 平台支持与行为说明

| 平台 | URL 示例 | 元数据获取 | 字幕/文稿机制 | ASR 行为 (`--enable-asr`) |
|---|---|---|---|---|
| **YouTube** | `https://www.youtube.com/watch?v=...`<br>`https://youtu.be/...` | yt-dlp (`-J`) | 优先官方字幕，无官方字幕则尝试自动字幕 | yt-dlp 音频下载 + FireRedASR2-AED 转录 |
| **Bilibili** | `https://www.bilibili.com/video/BV...`<br>`https://b23.tv/...` | yt-dlp (`-J`) | 优先官方字幕/AI字幕 | yt-dlp 音频下载 + FireRedASR2-AED 转录 |
| **微信视频号** | `https://weixin.qq.com/sph/...`<br>`https://channels.weixin.qq.com/...` | 腾讯内部预览接口 (匿名 `shortUri`) | 默认不含外挂字幕 (`unavailable`)；开启 ASR 时转录语音 | **复用本地 Chrome 元宝会话**，0 额外浏览器进程，下载媒体流并由 FireRedASR2-AED 转录 |

> [!NOTE]
> **关键设计语义**：
> 1. `no native transcript != extraction failure`：在默认模式下，微信视频号无需登录即可在毫秒级内导出包含作者、文案、封面及互动量的完整 Markdown。
> 2. **零手动凭证传输**：用户只要在日常 Chrome 浏览器中登录过腾讯元宝（`yuanbao.tencent.com`），开启 `--enable-asr` 后工具会自动按域名严格过滤会话 Cookie 并下载真实媒体流，完全无需手动复制 Cookie，无需开启桌面微信，无需 MITM 抓包。
> 3. **FireRedASR2-AED 离线中文模型**：2026 年新一代高精度模型，支持普通话、英语以及 20+ 种中文方言口音，完全无需 GPU 即可在 CPU 上高效执行 INT8 推理，零 API 调用成本。
> 4. **惰性模型加载 (Lazy Loading)**：执行 `./setup.sh` 时不下载 ~838 MB 的压缩模型包。模型仅在首次触发真实 ASR 请求时按需自动下载并进行 SHA-256 校验与原子部署。

---

## 3. 安装与使用

### 环境初始化

```bash
./setup.sh
```

此脚本会自动创建项目隔离的 `.venv/`，安装固定的 `sherpa-onnx==1.13.7` 官方预编译 Wheel，并检查 `ffmpeg`。

如果需要提前预下载并校验 ASR 离线模型，可执行：

```bash
.venv/bin/python scripts/prepare_asr_model.py
```

### 命令行使用 (`cli.py`)

```bash
# 1. 抓取单个链接 (微信视频号默认元数据模式，极速且无需登录，不触发 ASR 模型加载)
.venv/bin/python src/cli.py "https://weixin.qq.com/sph/AF17JEGHVd"

# 2. 微信视频号启用 ASR 语音识别 (自动读取本机 Chrome 登录态，转录完成后立即清理临时视频与 WAV 缓存)
.venv/bin/python src/cli.py "https://weixin.qq.com/sph/AF17JEGHVd" --enable-asr

# 3. 指定输出目录
.venv/bin/python src/cli.py "https://www.youtube.com/watch?v=_QdPW8JrYzQ" -o ./transcripts

# 4. 批量抓取多个链接
.venv/bin/python src/cli.py <url_1> <url_2> <url_3> -o ./output
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
transcript_method: "firered-asr2-aed"
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

刷到网友家的鹦鹉因为碗里的量不一样当场就不干了
```

---

## 5. 测试套件

运行完整离线测试套件：

```bash
.venv/bin/python -m unittest discover -s tests -p "test_*.py"
```
