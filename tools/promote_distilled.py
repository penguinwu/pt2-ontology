"""Manual promotion: distilled → reviewed.

Workflow:
1. Pipeline writes to ``ontology/distilled/<source>_<date>.json`` (the
   ``entries`` list).
2. Beaver audits the file and writes a companion
   ``ontology/distilled/<source>_<date>.audit.json`` of decisions.
3. Peng final-approves by setting ``approved_by`` + ``approved_at`` in
   that audit file.
4. Run::

       python3 -m tools.promote_distilled <source>_<date>.json [--apply]

   - Without ``--apply``: dry-run. Prints a per-target plan of what would
     change in ``ontology/entities/*.json`` and
     ``ontology/relationships/from_distilled.json``.
   - With ``--apply``: mutates the target files (atomic write) and
     appends one line per promoted batch to
     ``ontology/distilled/PROMOTIONS.log``.

Idempotency: if an entry's derived id already exists in the target file,
it is SKIPPED (logged, not overwritten). Edits go through the audit
file's ``patch`` field, not by re-running promote with new distilled
content.

Audit file shape (companion to distilled file)::

    {
      "audited_by": "Beaver",
      "audited_at": "2026-04-22T18:00:00Z",
      "approved_by": "Peng Wu",
      "approved_at": "2026-04-22T19:00:00Z",
      "decisions": {
        "0": {"decision": "approve"},
        "1": {"decision": "reject", "reason": "duplicate of 4"},
        "2": {"decision": "edit",
              "patch": {"name": "...", "detail": "..."}}
      }
    }

v0.1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from extractors.common.io import read_json  # noqa: E402

ENTITY_TYPE_TO_FILE = {
    "config": "ontology/entities/configs.json",
    "symptom": "ontology/entities/symptoms.json",
    "cause": "ontology/entities/causes.json",
}
RELATIONSHIPS_FILE = "ontology/relationships/from_distilled.json"
PROMOTIONS_LOG = "ontology/distilled/PROMOTIONS.log"
DEFAULT_VISIBILITY = "internal"


def slugify(text: str) -> str:
    """Lowercase, replace runs of non-alnum with underscore, trim."""
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "unnamed"


def derive_id(entry: dict) -> str:
    return entry.get("id_hint") or slugify(entry["name"])


def find_audit_file(distilled_path: Path) -> Path:
    """Companion file: foo.json -> foo.audit.json."""
    return distilled_path.with_suffix(".audit.json")


def load_audit(audit_path: Path) -> tuple[dict, dict]:
    """Return (audit_meta, decisions). Raises if not human-approved."""
    audit = read_json(audit_path)
    if not audit.get("approved_by") or not audit.get("approved_at"):
        raise RuntimeError(
            f"audit file {audit_path} is not approved yet "
            "(missing approved_by / approved_at)"
        )
    return audit, audit.get("decisions", {})


def build_entity_record(distilled: dict, patch: Optional[dict],
                        audit: dict) -> dict:
    base = dict(distilled)
    if patch:
        base.update(patch)
    eid = derive_id(base)
    desc = base.get("detail") or base.get("evidence", "")
    return {
        "id": eid,
        "name": base["name"],
        "description": desc,
        "visibility": base.get("visibility", DEFAULT_VISIBILITY),
        "provenance": {
            "source_type": "llm_distilled",
            "audited_by": audit.get("audited_by"),
            "audited_at": audit.get("audited_at"),
            "approved_by": audit.get("approved_by"),
            "approved_at": audit.get("approved_at"),
            "evidence": base.get("evidence"),
            "llm_provenance": distilled.get("llm_provenance"),
            "edited": bool(patch),
        },
    }


def build_relationship_record(distilled: dict, patch: Optional[dict],
                              audit: dict) -> dict:
    base = dict(distilled)
    if patch:
        base.update(patch)
    return {
        "from": slugify(base["name"]),
        "to": slugify(base.get("relationship_to", "")),
        "type": base.get("relationship_kind"),
        "description": base.get("detail") or base.get("evidence", ""),
        "visibility": base.get("visibility", DEFAULT_VISIBILITY),
        "provenance": {
            "source_type": "llm_distilled",
            "audited_by": audit.get("audited_by"),
            "audited_at": audit.get("audited_at"),
            "approved_by": audit.get("approved_by"),
            "approved_at": audit.get("approved_at"),
            "evidence": base.get("evidence"),
            "llm_provenance": distilled.get("llm_provenance"),
            "edited": bool(patch),
        },
    }


def existing_ids(records: list[dict]) -> set[str]:
    return {r.get("id") for r in records if r.get("id")}


def existing_edge_keys(records: list[dict]) -> set[tuple]:
    return {(r.get("from"), r.get("to"), r.get("type")) for r in records}


def atomic_write_canonical(path: Path, data) -> None:
    """Write to a temp file in the same dir then rename, so a crash never
    leaves a half-written entity file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as f:
        json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
        tmp = Path(f.name)
    os.replace(tmp, path)


def promote(distilled_path: Path, dry_run: bool = True) -> dict:
    distilled_path = Path(distilled_path).resolve()
    if not distilled_path.exists():
        raise FileNotFoundError(distilled_path)
    distilled = read_json(distilled_path)
    entries = distilled["entries"]
    audit_path = find_audit_file(distilled_path)
    if not audit_path.exists():
        raise FileNotFoundError(
            f"audit file not found: {audit_path}\n"
            "Beaver must produce one and Peng must sign it before promotion."
        )
    audit, decisions = load_audit(audit_path)

    grouped: dict[str, list[tuple[dict, Optional[dict]]]] = {}
    rejected: list[tuple[int, str]] = []
    skipped_no_decision: list[int] = []
    for i, e in enumerate(entries):
        d = decisions.get(str(i))
        if not d:
            skipped_no_decision.append(i)
            continue
        decision = d.get("decision")
        if decision == "reject":
            rejected.append((i, d.get("reason", "")))
            continue
        if decision not in ("approve", "edit"):
            raise ValueError(f"entry {i}: unknown decision {decision!r}")
        patch = d.get("patch") if decision == "edit" else None
        et = e["entity_type"]
        if et == "relationship":
            target = RELATIONSHIPS_FILE
        else:
            target = ENTITY_TYPE_TO_FILE.get(et)
            if not target:
                raise ValueError(f"entry {i}: unknown entity_type {et!r}")
        grouped.setdefault(target, []).append((e, patch))

    plan = {
        "distilled": str(distilled_path),
        "audit": str(audit_path),
        "n_entries": len(entries),
        "rejected": rejected,
        "skipped_no_decision": skipped_no_decision,
        "files": {},
    }

    for target, items in grouped.items():
        target_path = REPO_ROOT / target
        existing = read_json(target_path) if target_path.exists() else []
        if target == RELATIONSHIPS_FILE:
            keys = existing_edge_keys(existing)
            new_records, dupes = [], []
            for e, patch in items:
                rec = build_relationship_record(e, patch, audit)
                k = (rec["from"], rec["to"], rec["type"])
                if k in keys:
                    dupes.append(k)
                else:
                    keys.add(k)
                    new_records.append(rec)
        else:
            ids = existing_ids(existing)
            new_records, dupes = [], []
            for e, patch in items:
                rec = build_entity_record(e, patch, audit)
                if rec["id"] in ids:
                    dupes.append(rec["id"])
                else:
                    ids.add(rec["id"])
                    new_records.append(rec)
        plan["files"][target] = {
            "existing_count": len(existing),
            "to_add": len(new_records),
            "duplicates_skipped": dupes,
            "after_count": len(existing) + len(new_records),
        }
        if not dry_run and new_records:
            merged = existing + new_records
            atomic_write_canonical(target_path, merged)

    if not dry_run:
        log_path = REPO_ROOT / PROMOTIONS_LOG
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "promoted_at": ts,
                "distilled": str(distilled_path.relative_to(REPO_ROOT)),
                "audit": str(audit_path.relative_to(REPO_ROOT)),
                "audited_by": audit.get("audited_by"),
                "approved_by": audit.get("approved_by"),
                "files": {t: info["to_add"]
                          for t, info in plan["files"].items()},
                "rejected": [i for i, _ in rejected],
                "skipped_no_decision": skipped_no_decision,
            }, sort_keys=True, ensure_ascii=False) + "\n")

    return plan


def print_plan(plan: dict, applied: bool) -> None:
    verb = "APPLIED" if applied else "DRY-RUN"
    print(f"=== promote_distilled [{verb}] ===", file=sys.stderr)
    print(f"distilled: {plan['distilled']}", file=sys.stderr)
    print(f"audit:     {plan['audit']}", file=sys.stderr)
    print(f"entries:   {plan['n_entries']}", file=sys.stderr)
    if plan["rejected"]:
        print(f"rejected:  {len(plan['rejected'])}", file=sys.stderr)
        for i, reason in plan["rejected"]:
            print(f"  - [{i}] {reason}", file=sys.stderr)
    if plan["skipped_no_decision"]:
        print(
            f"skipped (no audit decision): {plan['skipped_no_decision']}",
            file=sys.stderr,
        )
    for target, info in plan["files"].items():
        print(
            f"  {target}: {info['existing_count']} -> {info['after_count']} "
            f"(+{info['to_add']}, skipped {len(info['duplicates_skipped'])} dupes)",
            file=sys.stderr,
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("distilled_file", type=Path,
                   help="Path to ontology/distilled/<source>_<date>.json")
    p.add_argument("--apply", action="store_true",
                   help="Without this flag, runs as dry-run (no writes).")
    args = p.parse_args()
    plan = promote(args.distilled_file, dry_run=not args.apply)
    print_plan(plan, applied=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
