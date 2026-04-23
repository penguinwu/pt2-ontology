"""Snapshot a Google Chat space to a frozen, content-hashed JSON file.

Why a snapshot (vs. live read each run): the cache key in llm_client.py
includes the input text. If we read live each time, every minor message
edit invalidates the cache and re-bills llmvm. Snapshotting decouples
"refresh the input" from "rerun the LLM."

Layout:
  snapshots/<source>_<YYYY_MM_DD>_<sha12>.json   — frozen content
  snapshots/<source>_latest.json                  — symlink to current

Each snapshot is a list of message dicts in chronological order with only
the fields the LLM needs (no pii_blob / no internal IDs).

Usage:
  python -m extractors.llm_distill.snapshot_chat \\
      --space <SPACE_ID> --source dynamo_chat --since 30d
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "extractors/llm_distill/snapshots"

# Fields kept in each snapshot record. Drop sender_work_user_fbid: it's a PII
# proxy and the LLM doesn't need it. Keep sender_name (publicly visible in
# space) for relationship/attribution context.
KEEP_FIELDS = (
    "creation_timestamp",
    "google_message_name",
    "google_thread_name",
    "is_thread_reply",
    "parent_google_message_name",
    "sender_name",
    "message_body",
)


def fetch_messages(space_id: str, since: str, count: int) -> list[dict]:
    """Call `gchat read` and return the parsed message list."""
    cmd = [
        "gchat", "read", space_id,
        "--since", since,
        "--count", str(count),
        "--quiet",
        "--json",
        "--oldest",  # chronological order — easier for LLM
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"gchat read failed (rc={result.returncode}): {result.stderr[-500:]}"
        )
    payload = json.loads(result.stdout)
    if not payload.get("success"):
        raise RuntimeError(f"gchat read returned success=false: {payload}")
    return payload["data"]["data"]


def canonicalize(messages: list[dict]) -> list[dict]:
    """Project to KEEP_FIELDS and sort by creation_timestamp ascending.
    Determinism matters: same input → same canonical bytes → same hash."""
    cleaned = []
    for m in messages:
        cleaned.append({k: m.get(k) for k in KEEP_FIELDS})
    cleaned.sort(key=lambda r: (r["creation_timestamp"] or 0, r["google_message_name"] or ""))
    return cleaned


def write_snapshot(records: list[dict], source: str, dest_dir: Path) -> Path:
    """Write canonical JSON, content-hash, and update the latest-symlink."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    canon = json.dumps(records, sort_keys=True, ensure_ascii=False, indent=2)
    sha12 = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]
    today = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    out_path = dest_dir / f"{source}_{today}_{sha12}.json"
    out_path.write_text(canon)
    latest = dest_dir / f"{source}_latest.json"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(out_path.name)
    return out_path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--space", required=True, help="Google Chat space ID (declared in INPUTS.md)")
    p.add_argument("--source", required=True, help="Slug for filenames (e.g., dynamo_chat)")
    p.add_argument("--since", default="30d", help="Lookback window (default: 30d)")
    p.add_argument("--count", type=int, default=2000, help="Max messages (default: 2000)")
    p.add_argument("--dest", type=Path, default=SNAPSHOT_DIR, help="Destination dir")
    args = p.parse_args()

    msgs = fetch_messages(args.space, args.since, args.count)
    canon = canonicalize(msgs)
    out = write_snapshot(canon, args.source, args.dest)
    print(f"wrote {out} ({len(canon)} messages)", file=sys.stderr)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
