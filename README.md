# Tools — Capability Implementation Monorepo

`SentimentalK/tools` is a **capability implementation monorepo** designed to provide stable, versioned capabilities to the **Chief Everything Officer (CEO)** platform and autonomous agents.

---

## 1. Core Architecture Principles

> **A capability is a stable semantic contract.**
> Docker containers, Python packages, host-native executables, and internal HTTP services are execution mechanisms, not capability identities.

One capability package in this monorepo may produce one or more execution artifacts depending on runtime requirements:

```text
                               Tools Monorepo
                                      │
                         ┌────────────┴────────────┐
                         │   subtitle-extractor    │
                         └────────────┬────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
        content.resolve_url                       content.extract_url
        ───────────────────                       ───────────────────
        Execution: Sync HTTP Service              Execution: Async Worker (Future CEO Worker)
        Runtime: Lightweight, stateless          Runtime: Heavy, state-sensitive
        Latency: <300ms typical                   Latency: Long-form ingestion (seconds/minutes)
        Packaging: OCI container (python-slim)    Packaging: Host-native / local compute
        Dependencies: httpx, yt-dlp, fastapi      Dependencies: + sherpa-onnx, numpy, cookies
```

---

## 2. Capability Catalog

| Capability | Tool Package | Execution Profile | Description |
|---|---|---|---|
| `content.resolve_url` | `subtitle-extractor` | Synchronous HTTP Service | Fast, read-only metadata resolution for YouTube, Bilibili, and WeChat Channels without downloading media or loading ASR. |
| `content.extract_url` | `subtitle-extractor` | Asynchronous Worker / CLI | Autonomous full extraction: metadata -> native subtitles if available -> media acquisition + host-native FireRedASR2-AED offline speech recognition. |
| `document.pptx_to_md` | `pptx-to-md` | CLI / Library | Local-first PPTX extraction and structured Markdown generation with embedded PaddleOCR-ONNX. |

---

## 3. Subtitle Extractor Runtime Boundaries

### `content.resolve_url` (Provider-Side HTTP Service)
- **Deployment**: Runs as a lightweight, stateless, always-on internal service on provider infrastructure (e.g. K3s / homelab).
- **Semantics**: "Tell me what this URL is."
- **Hard Boundaries**:
  - Strictly read-only network calls.
  - Zero browser cookies or Chrome session access.
  - Zero media or subtitle downloads.
  - Zero ASR model loading or download overhead.
  - Zero temporary files.
- **Fail-Closed Readiness**:
  - `/healthz`: process liveness probe (200 OK).
  - `/readyz`: readiness probe verifying `TOOLS_INTERNAL_TOKEN` (200 if configured, 503 if missing).
  - `/v1/resolve`: authenticated endpoint requiring `Authorization: Bearer <token>`.

### `content.extract_url` (Future CEO Worker Capability)
- **Deployment**: Executes host-native on worker machines with access to local browser sessions or compute.
- **Semantics**: "Give me the actual usable content behind this URL."
- **Ownership**:
  - Worker = computation (media download, browser cookies, FireRedASR2 ASR).
  - CEO Platform = orchestration, validation, and canonical Git write.

---

## 4. Quickstart

### Running the Resolver Service Locally

```bash
cd subtitle-extractor
./setup.sh

# Set internal service token and start uvicorn
export TOOLS_INTERNAL_TOKEN="your-internal-secret-token"
.venv/bin/uvicorn src.service:app --host 0.0.0.0 --port 8000
```

Verify service:
```bash
# Check health and readiness
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz

# Resolve a WeChat Channels URL
curl -X POST http://localhost:8000/v1/resolve \
  -H "Authorization: Bearer your-internal-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"schema_version": 1, "url": "https://weixin.qq.com/sph/AF17JEGHVd"}'
```

### Running the Resolver in Docker / K3s

Build OCI image:
```bash
docker build -t ghcr.io/sentimentalk/content-resolver:latest -f subtitle-extractor/Dockerfile subtitle-extractor/
```

Deploy to K3s:
```bash
kubectl apply -f subtitle-extractor/deploy/k8s-resolver.yaml
```

---

## 5. Python API Usage

```python
from subtitle_extractor import resolve_url, extract_url

# 1. Lightweight, fast metadata resolution (zero ASR, zero cookies)
metadata = resolve_url("https://weixin.qq.com/sph/AF17JEGHVd")
print(metadata.title, metadata.creator, metadata.like_count)

# 2. Autonomous full content extraction (metadata -> native subs -> FireRedASR2-AED fallback)
content = extract_url("https://weixin.qq.com/sph/AF17JEGHVd")
print(content.transcript_status)  # "available"
print(content.transcript)         # full transcribed speech text
```
