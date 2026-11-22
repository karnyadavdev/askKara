#!/bin/bash
set -euo pipefail

DB=/opt/askkara/kara.db
DIR=/var/backups/askkara
KEEP=7

mkdir -p "$DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$DIR/kara-$STAMP.db.gz"

/usr/bin/python3 - "$DB" /tmp/kara-snap.db <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close()
src.close()
PY

gzip -c /tmp/kara-snap.db > "$OUT"
rm -f /tmp/kara-snap.db

ls -1t "$DIR"/kara-*.db.gz | tail -n +$((KEEP + 1)) | xargs -r rm -f

echo "backup ok: $OUT ($(du -h "$OUT" | cut -f1))"
