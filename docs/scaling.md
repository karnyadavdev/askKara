# Scaling

Where AskKara breaks as it grows, and what I'd change at each step.

## Today (one box, demo traffic)

nginx + FastAPI + SQLite on a single EC2 behind CloudFront. Fine for hundreds of users a day. This is the weakest point: one box is both the web server and the database.

## 10x: more traffic on the same box

- CloudFront caching already absorbs static assets; add short-TTL caching for `GET` endpoints like history and health.
- uvicorn workers: 1 process → 4, which is also the point where SQLite's single-writer limit starts to matter.
- Move to Postgres (RDS or self-hosted) — the app already goes through SQLAlchemy, so it's a connection string and an import, not a rewrite. Trigger: concurrent writes or a second app server.

## 100x: separate the pieces

- Stateless API servers behind an ALB, autoscaled. Nothing on them is local — that's why avatars go to object storage, not disk.
- Postgres primary + read replica; reads (history, feed) go to the replica.
- The research loop is the expensive part: a worker queue (Celery/RQ) so a slow scrape doesn't hold an HTTP connection. SSE becomes a pub/sub channel the API reads from.
- Scraper farm: YADA is CPU/IO heavy and gets rate-limited by targets, so it runs as its own service with its own limits.

## What stays the same

- SSE protocol and the five event types — the transport changes (pub/sub instead of in-process), the contract doesn't.
- Cite every claim back to a URL. That's the product, not infrastructure.

## Honest limits

Nothing here has been tested past a handful of concurrent users. The steps above are the standard playbook, not battle-tested on this codebase — the first real bottleneck would probably be the LLM provider rate limits, not the servers.
