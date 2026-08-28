"""
push_to_supabase.py
--------------------
Generic pusher used by ALL 5 strategy scanners. Each scanner just needs to
produce a pandas DataFrame with these columns (extra strategy-specific
columns are automatically folded into a JSON 'extra' field):

    ticker, score, stage, entry, stop, target   (all optional except ticker)

Usage inside any scanner script, e.g. vcp_case_study_analyzer.py:

    from push_to_supabase import push_scan_results
    push_scan_results(df, strategy="VCP")

Requires env var SUPABASE_SERVICE_KEY (service_role key, NOT the anon key —
service_role bypasses RLS so GitHub Actions can insert; this key must never
be shipped to the frontend, keep it only in GitHub Secrets).
Also requires SUPABASE_URL env var, e.g. https://xxxx.supabase.co
"""

import os
import json
from datetime import date, timedelta

import pandas as pd
import requests

KNOWN_COLS = {"ticker", "score", "stage", "entry", "stop", "target"}

# How many days of untracked scan history to keep around for review before
# auto-deleting. Rows the user has tapped "track" on (tracked=true) are
# skipped by this cleanup for as long as they stay tracked — the user can
# permanently delete a tracked stock (and its scan row) anytime from the
# Watchlist's Delete button, which also un-marks tracked so it falls back
# into normal cleanup rotation.
RETENTION_DAYS = 10


def push_scan_results(df: pd.DataFrame, strategy: str, scan_date: str = None):
    """
    Upserts one day's scan results for a given strategy into Supabase.
    Safe to re-run for the same day (unique constraint upserts, no dupes).
    Also prunes untracked scan rows older than RETENTION_DAYS to keep the
    table small — tracked rows (already promoted to the watchlist) are
    never deleted here.
    """
    if df.empty:
        print(f"[{strategy}] No rows to push — empty DataFrame, skipping.")
        return

    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_KEY"]
    scan_date = scan_date or str(date.today())

    rows = []
    for _, r in df.iterrows():
        row = {"scan_date": scan_date, "strategy": strategy}
        extra = {}
        for col, val in r.items():
            if pd.isna(val):
                val = None
            if col in KNOWN_COLS:
                row[col] = val
            else:
                extra[col] = val
        row["extra"] = extra
        rows.append(row)

    endpoint = f"{supabase_url}/rest/v1/scan_results"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",  # upsert on the unique constraint
    }

    resp = requests.post(endpoint, headers=headers, data=json.dumps(rows))
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"[{strategy}] Push failed ({resp.status_code}): {resp.text}")

    print(f"[{strategy}] Pushed {len(rows)} rows for {scan_date}.")

    try:
        _cleanup_old_scans(supabase_url, service_key)
    except Exception as e:
        print(f"[{strategy}] Cleanup skipped (non-fatal): {type(e).__name__}: {e}")


def _cleanup_old_scans(supabase_url: str, service_key: str):
    """Deletes untracked scan_results rows older than RETENTION_DAYS."""
    cutoff = str(date.today() - timedelta(days=RETENTION_DAYS))
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    resp = requests.delete(
        f"{supabase_url}/rest/v1/scan_results",
        headers=headers,
        params={"scan_date": f"lt.{cutoff}", "tracked": "eq.false"},
    )
    if resp.status_code not in (200, 204):
        print(f"Cleanup request returned {resp.status_code}: {resp.text}")
    else:
        print(f"Cleanup: removed untracked scans older than {cutoff}.")


if __name__ == "__main__":
    # Quick manual test
    sample = pd.DataFrame([
        {"ticker": "RELIANCE", "score": 92, "stage": "Stage 2 breakout", "entry": 2950, "stop": 2870, "target": 3150},
        {"ticker": "TATASTEEL", "score": 81, "stage": "Late IB add-on", "entry": 165, "stop": 158, "target": 182},
    ])
    push_scan_results(sample, strategy="VCP")
