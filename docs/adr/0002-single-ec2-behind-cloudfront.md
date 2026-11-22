# 0002. One EC2 box behind CloudFront

**Status:** accepted

## Context

Full AWS (ECS, RDS, ALB) is more machinery than one demo needs, and it bills while idle. The account is also under an org policy that denies S3 and EC2 profile changes, which rules out several managed options anyway.

## Decision

One EC2 instance runs nginx + systemd + FastAPI. CloudFront sits in front for TLS and caching. GitHub Actions deploys over SSH: rsync the code, run migrations, restart, health-check, invalidate the cache.

## Consequences

- Cheap, understandable, and one `ssh` away when something breaks.
- Single point of failure: if the box dies, the site is down until it's replaced. Acceptable for a demo; would be the first thing to change under real traffic.
- Deploys are atomic per step (backend first, then frontend) with a `.prev` copy for quick rollback.
