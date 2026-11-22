# 0001. SQLite instead of Postgres

**Status:** accepted

## Context

One server, one process, low write volume. Postgres means another service to install, patch, back up, and secure on a box that already runs nginx, FastAPI, and YADA.

## Decision

Use SQLite (`kara.db`) with SQLAlchemy and Alembic. No raw SQL in the app.

## Consequences

- Zero ops. Backups are a file snapshot (see `deploy/db-backup.sh`).
- No concurrent writers — fine here, the app is read-heavy with a single worker.
- Moving to Postgres later is a connection-string swap plus a data import, because everything goes through the ORM. The day multiple workers or concurrent writes show up, that's the trigger to migrate.
