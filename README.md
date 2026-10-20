# AskKara

AskKara is a local research assistant: a React UI on a FastAPI service backed by the YADA scraper. It searches for sources, scrapes pages locally, and streams an answer with references.

## What It Does

- Accepts natural-language questions and direct URLs.
- Uses source discovery (DuckDuckGo via `ddgs`) when the question needs fresh or external information.
- Scrapes selected pages through YADA's HTTP layers only (`allow_browser=False`): fast and lightweight, no Playwright launch per source. YADA's browser layers remain available for the standalone YADA API.
- Streams the final answer into the interface with source references.
- Optional accounts (JWT). Guests can ask by default; set `KARA_AUTH_REQUIRED=1` to require sign-in.

## Setup

Backend:

```powershell
pip install -r requirements.txt
pip install -e ../YADA-Scraper-API
copy .env.example .env
```

Set `NIM_API_KEY` in `.env` (get a key at build.nvidia.com). Every setting is documented in `.env.example`.

Frontend:

```powershell
cd frontend
npm install
```

## Running Locally

Backend (port 4177):

```powershell
python backend.py
```

Frontend (port 5173, proxies `/api` to the backend):

```powershell
cd frontend
npm run dev
```

Then open:

```text
http://localhost:5173
```

## Backend Health

```text
http://127.0.0.1:4177/api/health
```

## Tests

```powershell
python -m pytest tests -q
cd frontend
npm run lint
npm run test
npm run build
```

## YADA Standalone API

Kara imports YADA directly, so the standalone YADA server is not required for the main demo. To show YADA separately (full ladder, including browser layers):

```powershell
cd path\to\YADA-Scraper-API
python yada_scraper.py
```

YADA runs at:

```text
http://127.0.0.1:8000
```
