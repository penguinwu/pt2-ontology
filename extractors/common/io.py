"""Canonical JSON I/O for reproducibility.

Same input + same extractor version → byte-identical output.
Sorted keys, stable indent, trailing newline.
"""
import json
from pathlib import Path
from typing import Any


def write_canonical_json(path: Path, data: Any) -> None:
    """Write JSON with sorted keys, 2-space indent, trailing newline.

    Determinism contract: re-running an extractor with the same inputs
    must produce a byte-identical file. Reviewers can trust that any
    diff in the output reflects a real change in inputs or extractor logic.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
