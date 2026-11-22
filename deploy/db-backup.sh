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

S3_STATUS=not-configured
if [ -f /opt/askkara/.env ]; then
  if ! /opt/askkara/.venv/bin/python - "$OUT" <<'PY'
import os, sys
from pathlib import Path

for line in Path("/opt/askkara/.env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import boto3

bucket = os.environ.get("KARA_AVATAR_BUCKET", "")
if not bucket:
    raise SystemExit("KARA_AVATAR_BUCKET not set")
name = Path(sys.argv[1]).name
boto3.client("s3", region_name=os.environ.get("KARA_AVATAR_REGION", "ap-southeast-2")).upload_file(
    sys.argv[1], bucket, f"backups/{name}"
)
print(f"s3 ok: backups/{name}")
PY
  then
    S3_STATUS=failed
  else
    S3_STATUS=ok
  fi
fi

echo "backup ok: $OUT ($(du -h "$OUT" | cut -f1)) s3=$S3_STATUS"
[ "$S3_STATUS" != failed ]
