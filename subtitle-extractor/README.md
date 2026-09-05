# Subtitle Extractor & URL Content Ingestion Scaffold

支持 YouTube、B站 (Bilibili) 与 **微信视频号 (WeChat Channels SPH)** 的音视频内容抓取、字幕提取、本地 2026 中文第一的 **FireRedASR2-AED** 离线语音识别与标准化 Markdown/YAML 结构化导出。

---

## 1. 架构与两大对外能力 (Two-Capability Design)

系统对外部调用者仅暴露两个极简能力，内部全自动调度：

```text
                  URL
                   │
            ┌──────┴──────┐
            │             │
       resolve_url   extract_url
            │             │
            ↓             ↓
     ContentMetadata  ResolvedContent
```

### 能力 A: `resolve` (URL → 元数据解析)
- **语义**：“告诉我这个 URL 是什么。”
- **特点**：轻量、极速（毫秒级）、只读网络请求。**绝不读取浏览器 Cookie，绝不下载音视频或字幕文件，绝不触发 ASR 离线模型加载，绝不产生临时文件**。
- **Python API**：`resolve_url(url: str) -> ContentMetadata`
- **CLI**：`python src/cli.py resolve <URL>`（标准输出机器友好的纯 JSON，适合管道传输）

### 能力 B: `extract` (URL → 完整内容提取)
- **语义**：“给我这个 URL 的最终完整内容。”
- **特点**：全自主调度。自动获取元数据 → 探测原生字幕 → 若无原生字幕，自动获取媒体流（微信视频号复用本机 Chrome 元宝会话，YouTube/B站通过媒体下载器）并调用本机离线 **FireRedASR2-AED** 语音识别转录 → 生成最终结构化结果。完全自包含，无需事先调用 `resolve`。
- **Python API**：`extract_url(url: str, browser_name="chrome", profile_name="Default") -> ResolvedContent`
- **CLI**：`python src/cli.py extract <URL> [-o DIR] [--json]`（默认输出标准化 Markdown 文件；加 `--json` 打印结构化 JSON 数据）

---

### 运行时与项目目录结构

```text
subtitle-extractor/
├── .venv/                 # 宿主机本地 Python 虚拟环境 (由 setup.sh 创建)
├── .models/               # 本地自包含离线 ASR 模型 (Git 忽略)
│   ├── firered-asr2-aed-int8-2026-02-26/  # FireRedASR2-AED INT8 权重 (解压后约 1.2 GB)
│   └── silero_vad.onnx                    # Silero 语音活动检测模型
├── .tmp/                  # 项目本地运行时刮擦空间 (音频抽取、下载暂存，Git 忽略)
├── setup.sh               # 宿主机环境一键配置脚本
├── requirements.txt       # sherpa-onnx==1.13.7, yt-dlp, httpx, numpy, cryptography, secretstorage
├── scripts/
│   └── prepare_asr_model.py # 显式预下载/校验模型辅助脚本
├── src/
│   ├── __init__.py          # 顶层导出 resolve_url, extract_url, ContentMetadata, ResolvedContent
│   ├── api.py               # 公开稳定 API (resolve_url, extract_url)
│   ├── cli.py               # 命令行统一入口 (resolve / extract 子命令)
│   ├── pipeline.py          # 内部流程编排管线
│   ├── models.py            # 数据模型与错误定义 (ResolveError, UnsupportedURLError)
│   ├── model_manager.py     # 模型生命周期管理 (校验和验证、安全解压、原子替换)
│   ├── asr.py               # 离线 FireRedASR2-AED + Silero VAD 语音识别模块
│   ├── markdown.py          # YAML Front Matter 生成与 Markdown 导出
│   ├── adapters/            # 平台解析适配器 (纯匿名元数据抓取)
│   └── media/               # 媒体获取提供者 (隔离认证与媒体流下载)
└── tests/                   # 完整离线单元测试套件
```

---

## 2. 平台支持与行为说明

| 平台 | URL 示例 | 元数据获取 (`resolve`) | 字幕/文稿机制 (`extract`) | ASR 兜底行为 (`extract`) |
|---|---|---|---|---|
| **YouTube** | `https://www.youtube.com/watch?v=...`<br>`https://youtu.be/...` | yt-dlp (`-J`) 纯元数据 | 优先官方字幕，无官方字幕则尝试自动字幕 | yt-dlp 音频下载 + FireRedASR2-AED 转录 |
| **Bilibili** | `https://www.bilibili.com/video/BV...`<br>`https://b23.tv/...` | yt-dlp (`-J`) 纯元数据 | 优先官方字幕/AI字幕 | yt-dlp 音频下载 + FireRedASR2-AED 转录 |
| **微信视频号** | `https://weixin.qq.com/sph/...`<br>`https://channels.weixin.qq.com/...` | 腾讯内部预览接口 (匿名 `shortUri`) | 默认无外挂字幕 | **复用本地 Chrome 元宝会话**，0 额外浏览器进程，下载媒体流并由 FireRedASR2-AED 转录 |

> [!NOTE]
> **关键设计语义**：
> 1. **两层解耦**：`resolve_url` 耗时 <300ms，适合做 URL 侦测与卡片预览；`extract_url` 全自动完成内容与音频下沉转录。
> 2. **零手动凭证传输**：用户只要在日常 Chrome 浏览器中登录过腾讯元宝（`yuanbao.tencent.com`），`extract` 会自动按域名严格过滤会话 Cookie 并下载真实媒体流，完全无需手动复制 Cookie，无需开启桌面微信，无需 MITM 抓包。
> 3. **FireRedASR2-AED 离线中文模型**：2026 年新一代高精度模型，支持普通话、英语以及 20+ 种中文方言口音，完全无需 GPU 即可在 CPU 上高效执行 INT8 推理，零 API 调用成本。
> 4. **惰性模型加载 (Lazy Loading)**：执行 `./setup.sh` 时不下载模型包。模型仅在首次触发真实 ASR 请求时按需自动下载并进行 SHA-256 校验与原子部署。

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

### Python API 使用

```python
from src import resolve_url, extract_url

# 1. 仅解析元数据 (极速，零副作用，不下载媒体，不触碰 Cookie，不加载 ASR)
metadata = resolve_url("https://weixin.qq.com/sph/AF17JEGHVd")
print(metadata.title, metadata.creator, metadata.like_count)

# 2. 完整内容提取 (全自主：元数据 + 原生字幕/FireRedASR2 离线转录)
content = extract_url("https://weixin.qq.com/sph/AF17JEGHVd")
print(content.transcript_status)  # "available"
print(content.transcript)         # 转录后的全文文本
```

### 命令行使用 (`cli.py`)

#### 1. `resolve` 子命令 (输出标准 JSON)
```bash
# 解析单个链接元数据 (纯 JSON 输出到 stdout，方便 jq 或下游消费)
.venv/bin/python src/cli.py resolve "https://weixin.qq.com/sph/AF17JEGHVd"

# 压缩 JSON 单行格式
.venv/bin/python src/cli.py resolve "https://weixin.qq.com/sph/AF17JEGHVd" --compact
```

#### 2. `extract` 子命令 (完整提取与导出)
```bash
# 提取内容并保存为 Markdown 到指定目录 (有原生字幕用原生字幕，无原生字幕自动 ASR)
.venv/bin/python src/cli.py extract "https://weixin.qq.com/sph/AF17JEGHVd" -o ./output

# 以 JSON 格式输出到 stdout
.venv/bin/python src/cli.py extract "https://weixin.qq.com/sph/AF17JEGHVd" --json

# 批量提取多个链接
.venv/bin/python src/cli.py extract <url_1> <url_2> <url_3> -o ./output
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
