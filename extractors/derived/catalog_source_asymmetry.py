"""Derived view: graph-break catalog ⟂ source-mined causes asymmetry.

Joins two extractor outputs by short-name / gb_type:
  - extractors/graph_break_site/output/graph_break_catalog.json (455 GB####)
  - extractors/pytorch_source/output/causes_from_unimplemented.json (412 sites)

Emits a single derived JSON with three buckets:
  - matched:       catalog entry + source site(s) for the same gb_type
  - catalog_only:  GB#### entries with no exact-match source site
                   (likely renames, formatting drift in the rendered HTML,
                   or call sites we didn't walk yet)
  - source_only:   source gb_type literals with no matching catalog entry
                   (likely newer than the snapshot, or dynamic strings)

This view is the "audit-page asymmetry" applied to source-of-truth mining:
it surfaces the join failures so the consumer can prioritize alias
normalization (strip backticks, normalize __name__, etc.) without
re-mining from scratch.

Reproducibility: a pure function of the two input JSONs. Re-run to refresh.

Run:
    python -m extractors.derived.catalog_source_asymmetry
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from extractors.common.base import Extractor  # noqa: E402
from extractors.common.io import read_json  # noqa: E402
from extractors.common.provenance import file_sha256  # noqa: E402

CATALOG_PATH = "extractors/graph_break_site/output/graph_break_catalog.json"
CAUSES_PATH = "extractors/pytorch_source/output/causes_from_unimplemented.json"


def _normalize(s: str) -> str:
    """Soft normalization for fuzzy join debugging.

    Strips backticks, asterisks, and double-underscores around identifiers.
    NOT applied to the primary join — kept here so the consumer can
    optionally enable it. The asymmetry view itself uses exact-match.
    """
    s = s.replace("`", "")
    s = s.replace("__", "")
    s = " ".join(s.split())
    return s


class CatalogSourceAsymmetryView(Extractor):
    extractor_id = "derived.catalog_source_asymmetry"
    extractor_version = "1.0.0"
    output_path = "extractors/derived/output/catalog_source_asymmetry.json"

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or REPO_ROOT)
        self.catalog_file = self.repo_root / CATALOG_PATH
        self.causes_file = self.repo_root / CAUSES_PATH
        for p in (self.catalog_file, self.causes_file):
            if not p.exists():
                raise FileNotFoundError(p)
        self._cat_sha12 = file_sha256(self.catalog_file)[:12]
        self._cau_sha12 = file_sha256(self.causes_file)[:12]

    def source_ref(self) -> str:
        return (
            f"catalog@{self._cat_sha12} ⟂ causes@{self._cau_sha12}"
        )

    def extracted_at(self) -> str:
        # Anchor to the *latest* extracted_at across the two input JSONs.
        # Their provenance is content-derived (source_sha / commit timestamp),
        # so this is stable across reruns even if file mtimes churn.
        catalog = read_json(self.catalog_file)
        causes = read_json(self.causes_file)
        ts_candidates: list[str] = []
        for arr in (catalog, causes):
            for e in arr:
                t = e.get("provenance", {}).get("extracted_at")
                if t:
                    ts_candidates.append(t)
                    break  # one per input is enough; provenance is uniform
        if not ts_candidates:
            return "unknown"
        return max(ts_candidates)

    def extract(self) -> list[dict]:
        catalog = read_json(self.catalog_file)
        causes = read_json(self.causes_file)

        # Index source causes by gb_type.
        causes_by_gb: dict[str, list[dict]] = defaultdict(list)
        for c in causes:
            gb = c.get("gb_type")
            if isinstance(gb, str) and gb:
                causes_by_gb[gb].append(c)

        # Index catalog by short_name.
        catalog_by_name: dict[str, dict] = {e["short_name"]: e for e in catalog}

        catalog_names = set(catalog_by_name.keys())
        source_names = set(causes_by_gb.keys())

        matched_keys = sorted(catalog_names & source_names)
        catalog_only_keys = sorted(catalog_names - source_names)
        source_only_keys = sorted(source_names - catalog_names)

        matched = []
        for k in matched_keys:
            cat = catalog_by_name[k]
            src_sites = causes_by_gb[k]
            matched.append({
                "join_key": k,
                "catalog_id": cat["id"],
                "catalog_gbid": cat["name"],
                "catalog_url": cat["catalog_url"],
                "source_sites": [
                    {"id": s["id"], "source_location": s["source_location"]}
                    for s in src_sites
                ],
            })

        catalog_only = [
            {
                "join_key": k,
                "catalog_id": catalog_by_name[k]["id"],
                "catalog_gbid": catalog_by_name[k]["name"],
                "catalog_url": catalog_by_name[k]["catalog_url"],
                "normalized_join_key": _normalize(k),
            }
            for k in catalog_only_keys
        ]

        source_only = []
        for k in source_only_keys:
            sites = causes_by_gb[k]
            source_only.append({
                "join_key": k,
                "normalized_join_key": _normalize(k),
                "source_sites": [
                    {"id": s["id"], "source_location": s["source_location"]}
                    for s in sites
                ],
            })

        # Single-element list with the full asymmetry summary — matches the
        # Extractor contract (returns list[dict]).
        return [{
            "id": "catalog_source_asymmetry",
            "summary": {
                "catalog_count": len(catalog),
                "source_unique_gb_types": len(source_names),
                "matched": len(matched),
                "catalog_only": len(catalog_only),
                "source_only": len(source_only),
            },
            "matched": matched,
            "catalog_only": catalog_only,
            "source_only": source_only,
        }]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = p.parse_args()

    view = CatalogSourceAsymmetryView(repo_root=args.repo_root)
    out_path = view.run(args.repo_root)
    print(f"wrote {out_path}")
    print(f"  source: {view.source_ref()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
