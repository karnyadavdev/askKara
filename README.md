# AskKara

[![CI](https://github.com/karnyadavdev/askKara/actions/workflows/ci.yml/badge.svg)](https://github.com/karnyadavdev/askKara/actions/workflows/ci.yml)

AskKara is a research assistant that answers questions with live web sources. A React UI streams answers from a FastAPI backend, which discovers sources, scrapes pages through the [YADA scraper](https://github.com/karnyadavdev/YADA-Scraper-API), and cites every claim back to a URL.

**Live demo:** https://d24884eoij7cl7.cloudfront.net

## What it does

- Accepts natural-language questions and direct URLs.
- Discovers sources with DuckDuckGo (`ddgs`), with an optional freshness window so recent pages rank first.
- Scrapes pages through YADA's HTTP layers only (`allow_browser=False`): fast, no browser launch per source.
- Streams the answer as Server-Sent Events while a research loop runs in the background, with per-source citations.
- Two modes: **normal** (fast, few sources) and **deep** (multi-step research, digest per page, higher reasoning effort).
- Optional JWT accounts. Guests can ask by default; set `KARA_AUTH_REQUIRED=1` to require sign-in.

## Architecture

```
Browser (React 19 + Redux Toolkit, Vite 8, TypeScript 6)
   |  POST /api/ask/stream  ->  SSE: stage | step | token | ping | done
   v
FastAPI (kara/routers/ask.py)  rate limit, history window, SSE framing
   v
Agent loop (kara/agent/loop.py)  owns messages, sources, tool trace
   |            |             |
   v            v             v
web_search   yada_scrape   yada_scrape_many      (kara/agent/tools.py)
   |            |
ddgs          YADA scraper (import or HTTP mode)
                  |
                  v
            LLM provider chain (kara/llm/)  resilient failover, retries, effort levels
```

| component | role |
|---|---|
| `kara/routers/ask.py` | HTTP entry: question validation, rate limit (3 per 300 s per IP), history window, SSE stream |
| `kara/agent/loop.py` | The agent. Runs the tool loop, normalizes citations, returns the answer plus sources |
| `kara/agent/tools.py` | Tool schemas and runner, `SourceBudget` enforces source and character caps at execution time |
| `kara/agent/summarize.py` | Per-page digester: one low-effort LLM call per page, concurrency 3, lossless compression |
| `kara/scraper/yada.py` | YADA client and result normalization |
| `kara/scraper/pageclean.py` | Structural HTML cleaner: keeps tables, code, main content; caps page extras |
| `kara/llm/` | Provider abstraction: OpenAI-compatible, NIM, retry layer with sticky effort fallback |
| `kara/config.py` | Every setting, mapped from environment |

### Streaming protocol

The backend emits five SSE event types: `stage` (research phase label), `step` (narration), `token` (answer text), `ping` (keep-alive during long model silence), and `done` (final answer plus sources). There are deliberately no stream-reset events: the answer is never wiped mid-stream. Stage labels collapse into an archived disclosure in the UI, and the answer types in with a 2 to 12 ms per-character clamp.

The `ping` event matters in production: CloudFront's origin response timeout is an inter-packet timer, so a ping every 10 seconds keeps the connection alive even when the model thinks for minutes.

## Setup

Backend (Python 3.12):

```bash
pip install -r requirements.txt
pip install -e ../YADA-Scraper-API   # or set YADA_MODE=http and YADA_API_URL
cp .env.example .env
```

Set `NIM_API_KEY` in `.env` (get a key at build.nvidia.com). Every setting is documented in `.env.example`. YADA can run in-process (`YADA_MODE=import`), over HTTP against a separate YADA server (`YADA_MODE=http`), or off for tests (`YADA_MODE=off`).

Frontend (Node 24):

```bash
cd frontend
npm ci
```

## Running locally

Backend (port 4177):

```bash
python backend.py
```

Frontend (port 5173, proxies `/api` to the backend):

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. Health check: http://127.0.0.1:4177/api/health

## Tests

```bash
python -m pytest tests -q          # 205 backend tests
cd frontend
npm run lint                       # oxlint
npm run test                       # 28 frontend tests (vitest)
npm run build                      # tsc + vite
```

CI runs all of the above on every push to `main`.

## YADA Standalone API

AskKara imports YADA directly, so the standalone server is not required for the main demo. To run YADA separately (full strategy ladder including browser layers):

```bash
cd ../YADA-Scraper-API
python yada_scraper.py
```

YADA then runs at http://127.0.0.1:8000.

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), Alembic, httpx
- **Frontend:** React 19, Redux Toolkit, Vite 8, TypeScript 6, vitest, oxlint
- **Scraping:** YADA (curl_cffi TLS impersonation, Playwright fallback, strategy ladder)
- **LLM:** OpenAI-compatible providers with retry and failover (NIM, InferX, Groq, OpenAI)
- **Infra:** EC2 + nginx + systemd behind CloudFront
