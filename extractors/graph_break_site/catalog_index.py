"""Extract the graph-break catalog index → catalog_index alias entities.

Source: https://meta-pytorch.org/compile-graph-break-site/

Each entry on the index page is a graph-break catalog identifier (GB####)
plus a short human-readable name. The short name is the join key against
source-mined causes (see extractors/pytorch_source/unsupported_calls.py)
— Dynamo emits the same short string from `unimplemented(gb_type=...)`.

This extractor produces *pointer entities* — one per GB####, with:
  - id: `graph_break_<gbid_lower>` (e.g., "graph_break_gb0000")
  - name: GB#### identifier
  - short_name: plain-text title (the gb_type the source emits)
  - catalog_url: stable per-GB URL
  - testable_claims:
      - applies_when: short_name (matches the source-side explanation)
      - surface_signals: [short_name]
      - affects_compilation_phase: dynamo
      - verification_source: graph_break_site:GB####@snapshot:<sha12>

The index is reproduced from a pinned snapshot (snapshots/index_<sha12>.html),
not a live fetch — see INPUTS.md.

Run:
    python -m extractors.graph_break_site.catalog_index           # latest snapshot
    python -m extractors.graph_break_site.catalog_index --snapshot path/to/index.html
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from extractors.common.base import Extractor  # noqa: E402
from extractors.common.provenance import file_sha256  # noqa: E402

CATALOG_BASE = "https://meta-pytorch.org/compile-graph-break-site/"

# <li><a href="gb/gb0000.html">GB0000</a> — short name (may include HTML tags)</li>
_LI_RE = re.compile(
    r'<li><a href="gb/gb(\d+)\.html">GB\1</a>\s*[—-]\s*(.*?)</li>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    s = _TAG_RE.sub("", s)
    return " ".join(s.split())


def _latest_snapshot(snapshot_dir: Path) -> Optional[Path]:
    """Return the most-recently-modified snapshot file, or None."""
    if not snapshot_dir.exists():
        return None
    files = sorted(snapshot_dir.glob("index_*.html"))
    if not files:
        return None
    # Use lexicographic order on filename — sha-prefixed filenames are
    # already content-addressed, so picking max() is stable.
    return max(files, key=lambda p: p.stat().st_mtime)


class CatalogIndexExtractor(Extractor):
    extractor_id = "graph_break_site.catalog_index"
    extractor_version = "1.0.0"
    output_path = "extractors/graph_break_site/output/graph_break_catalog.json"

    def __init__(self, snapshot_path: Optional[Path] = None) -> None:
        snapshot_dir = Path(__file__).resolve().parent / "snapshots"
        self.snapshot_path = (
            Path(snapshot_path) if snapshot_path else _latest_snapshot(snapshot_dir)
        )
        if self.snapshot_path is None or not self.snapshot_path.exists():
            raise FileNotFoundError(
                f"No catalog snapshot found in {snapshot_dir}. "
                "Run `make snapshot-graph-break-site` first."
            )
        self._snapshot_sha = file_sha256(self.snapshot_path)
        self._snapshot_sha12 = self._snapshot_sha[:12]

    def source_ref(self) -> str:
        return f"graph_break_site@snapshot:{self._snapshot_sha12}"

    def extracted_at(self) -> str:
        # Use snapshot file mtime as a stable, source-bound timestamp.
        from datetime import datetime, timezone

        ts = datetime.fromtimestamp(
            self.snapshot_path.stat().st_mtime, tz=timezone.utc
        ).replace(microsecond=0)
        return ts.isoformat()

    def extract(self) -> list[dict]:
        html = self.snapshot_path.read_text(encoding="utf-8")
        out: list[dict] = []
        for gb_num, raw_name in _LI_RE.findall(html):
            short_name = _strip_html(raw_name)
            gb_id = f"GB{gb_num}"
            entity = {
                "id": f"graph_break_gb{gb_num.lower()}",
                "name": gb_id,
                "entity_type": "symptom",
                "short_name": short_name,
                "catalog_url": f"{CATALOG_BASE}gb/gb{gb_num}.html",
                "visibility": "oss",
                "testable_claims": {
                    "applies_when": short_name,
                    "surface_signals": [short_name],
                    "affects_compilation_phase": "dynamo",
                    "verification_source": (
                        f"graph_break_site:{gb_id}@snapshot:{self._snapshot_sha12}"
                    ),
                },
            }
            out.append(entity)
        out.sort(key=lambda e: e["id"])
        return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", type=Path, default=None,
                   help="Path to snapshot HTML (default: latest in snapshots/)")
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = p.parse_args()

    ex = CatalogIndexExtractor(snapshot_path=args.snapshot)
    out_path = ex.run(args.repo_root)
    print(f"wrote {out_path}")
    print(f"  source: {ex.source_ref()}")
    print(f"  snapshot: {ex.snapshot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
