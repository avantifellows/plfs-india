#!/usr/bin/env python3
"""
Upload JNV JEE and NEET data to GCS.

Uploads:
  - Raw mains:    each JEE Mains Excel → parquet
        gs://avantifellows-external-data/jnv/raw/jee_mains/<stem>.parquet
  - Raw advanced: each JEE Advanced Excel → parquet
        gs://avantifellows-external-data/jnv/raw/jee_advanced/<stem>.parquet
  - Raw NEET:     each NEET Excel → parquet
        gs://avantifellows-external-data/jnv/raw/neet/<stem>.parquet
  - Clean JEE:    jee_clean.csv → parquet
        gs://avantifellows-external-data/jnv/clean/jnv_fact_jee_results.parquet
  - Clean NEET:   neet_clean.csv → parquet
        gs://avantifellows-external-data/jnv/clean/jnv_fact_neet_results.parquet

Run clean_jee.py / clean_neet.py first to produce the clean CSVs.

Usage:
    python3 scripts/upload_to_gcs.py                    # upload all raw and clean
    python3 scripts/upload_to_gcs.py --raw-only
    python3 scripts/upload_to_gcs.py --clean-only
    python3 scripts/upload_to_gcs.py --jee-only         # JEE raw + clean
    python3 scripts/upload_to_gcs.py --neet-only        # NEET raw + clean
"""

import argparse
import io
import sys

import sys
from pathlib import Path

import pandas as pd
from google.cloud import storage

from sources import GCS_BUCKET, JEE_CLEAN, NEET_CLEAN, RAW_ADV_FILES, RAW_MAINS_FILES, RAW_NEET_FILES

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codemaps.neet.shared import apply_dtypes as apply_dtypes_neet
from codemaps.mains.shared import apply_dtypes as apply_dtypes_jee


def _upload(client, df: pd.DataFrame, gcs_path: str) -> None:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    bucket = client.bucket(GCS_BUCKET)
    bucket.blob(gcs_path).upload_from_file(buf, content_type="application/octet-stream")
    print(f"  ✓ gs://{GCS_BUCKET}/{gcs_path}  ({len(df):,} rows)")


def upload_raw_jee(client: storage.Client) -> None:
    print("Uploading raw mains files ...")
    for raw in RAW_MAINS_FILES:
        print(f"  Reading {raw.file} ...")
        df = pd.read_excel(raw.local_path, sheet_name=raw.sheet, dtype=str)
        _upload(client, df, raw.gcs_path)

    print("Uploading raw advanced files ...")
    for raw in RAW_ADV_FILES:
        print(f"  Reading {raw.file} ...")
        df = pd.read_excel(raw.local_path, sheet_name=raw.sheet, dtype=str)
        _upload(client, df, raw.gcs_path)


def upload_raw_neet(client: storage.Client) -> None:
    print("Uploading raw NEET files ...")
    for raw in RAW_NEET_FILES:
        print(f"  Reading {raw.file} ...")
        df = pd.read_excel(raw.local_path, sheet_name=raw.sheet, dtype=str)
        _upload(client, df, raw.gcs_path)


def upload_clean_jee(client: storage.Client) -> None:
    print("Uploading clean JEE file ...")
    if not JEE_CLEAN.local_path.exists():
        print(f"  ERROR: {JEE_CLEAN.local_path} not found.")
        print("  Run clean_jee.py first.")
        sys.exit(1)
    df = pd.read_csv(JEE_CLEAN.local_path, low_memory=False)
    df = apply_dtypes_jee(df)
    _upload(client, df, JEE_CLEAN.gcs_path)


def upload_clean_neet(client: storage.Client) -> None:
    print("Uploading clean NEET file ...")
    if not NEET_CLEAN.local_path.exists():
        print(f"  ERROR: {NEET_CLEAN.local_path} not found.")
        print("  Run clean_neet.py first.")
        sys.exit(1)
    df = pd.read_csv(NEET_CLEAN.local_path, low_memory=False)
    df = apply_dtypes_neet(df)
    _upload(client, df, NEET_CLEAN.gcs_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--raw-only",   action="store_true", help="Upload raw files only (JEE + NEET)")
    group.add_argument("--clean-only", action="store_true", help="Upload clean files only (JEE + NEET)")
    group.add_argument("--jee-only",   action="store_true", help="Upload JEE raw + clean")
    group.add_argument("--neet-only",  action="store_true", help="Upload NEET raw + clean")
    args = parser.parse_args()

    client = storage.Client()

    if args.raw_only:
        upload_raw_jee(client)
        upload_raw_neet(client)
    elif args.clean_only:
        upload_clean_jee(client)
        upload_clean_neet(client)
    elif args.jee_only:
        upload_raw_jee(client)
        upload_clean_jee(client)
    elif args.neet_only:
        upload_raw_neet(client)
        upload_clean_neet(client)
    else:
        upload_raw_jee(client)
        upload_raw_neet(client)
        upload_clean_jee(client)
        upload_clean_neet(client)

    print("\nDone.")


if __name__ == "__main__":
    main()
