"""
Upload parsed AISHE parquet files from clean/ to GCS.

Reads each parquet listed in sources.py from aishe/clean/ (produced by
clean_aishe.py) and uploads it to the canonical GCS path. Overwrites in
place — a refreshed AISHE report reuses the same filenames.

Usage:
  python3 scripts/upload_to_gcs.py                                  # all tables
  python3 scripts/upload_to_gcs.py --table aishe_fact_outturn_state_level
  python3 scripts/upload_to_gcs.py --dry-run                        # show plan only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import GCS_BUCKET, GCS_PREFIX, TABLES, Table


def _upload(table: Table, client, dry_run: bool) -> None:
    if not table.local_path.exists():
        raise SystemExit(
            f"missing local parquet: {table.local_path}\nRun scripts/clean_aishe.py first."
        )
    size_mb = table.local_path.stat().st_size / 1e6
    msg = f"{table.local_path.name} ({size_mb:.2f} MB) → {table.gcs_uri}"
    if dry_run:
        print(f"  [dry-run] {msg}")
        return
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(f"{GCS_PREFIX}/{table.parquet}")
    blob.upload_from_filename(str(table.local_path), content_type="application/octet-stream")
    print(f"  uploaded {msg}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", default=None, help="Upload only this BQ table name")
    ap.add_argument("--dry-run", action="store_true", help="Print plan; don't upload")
    args = ap.parse_args()

    chosen = TABLES
    if args.table:
        chosen = [t for t in TABLES if t.bq_name == args.table]
        if not chosen:
            raise SystemExit(f"unknown table {args.table!r}; known: {[t.bq_name for t in TABLES]}")

    client = None
    if not args.dry_run:
        from google.cloud import storage
        client = storage.Client()

    print(f"AISHE → gs://{GCS_BUCKET}/{GCS_PREFIX}/   ({'dry-run' if args.dry_run else 'upload'})")
    for t in chosen:
        _upload(t, client, args.dry_run)
    print("✓ done.")


if __name__ == "__main__":
    main()
