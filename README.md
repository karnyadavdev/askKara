# Kara

Kara is a local research assistant UI backed by a FastAPI service and the YADA scraper. It can search for sources, scrape pages locally, and synthesize an answer with references.

## What It Does

- Accepts natural-language questions and direct URLs.
- Uses source discovery (DuckDuckGo via `ddgs`) when the question needs fresh or external information.
- Scrapes selected pages through YADA's HTTP layers only (`allow_browser=False`) — fast and lightweight, no Playwright launch per source. YADA's browser layers remain available for the standalone YADA API.
- Streams the final answer into the interface with source references.
- Keeps the scraper in-process: `yada-scraper-api` is installed as a package dependency (`pip install -e ../YADA-Scraper-API` during development).

## Setup

- `pip install -r requirements` for the app plus `ddgs` (search) and the YADA package.
- `.env` must define `GEMINI_API_KEY` (plus optional `GEMINI_SEARCH_MODEL` / `GEMINI_ANSWER_MODEL`).

## Running Locally

```powershell
cd "C:\Users\Karan Yadav\Documents\improvement (1)\askKara-main (1)"
python backend.py
```

Then open:

```text
http://127.0.0.1:4177
```

## Backend Health

```text
http://127.0.0.1:4177/api/health
```

## YADA Standalone API

Kara imports YADA directly, so the standalone YADA server is not required for the main demo. To show YADA separately (full ladder, including browser layers):

```powershell
cd "C:\Users\Karan Yadav\Pictures\YADA-Scraper-API version3 (1) sept"
python yada_scraper.py
```

YADA runs at:

```text
http://127.0.0.1:8000
```
