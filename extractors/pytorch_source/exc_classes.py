"""Extract exception classes from torch/_dynamo/exc.py → symptom entities.

Each Dynamo exception class is a candidate symptom: a thing the user might
observe in logs/stack traces that signals a torch.compile failure mode.

For each class, we capture:
  - id: snake_case of the class name, prefixed with `dynamo_`
  - name: fully-qualified class name (`torch._dynamo.exc.<ClassName>`)
  - description: first line of the class docstring (or "" if none)
  - base_class: immediate parent class
  - source_line: line number in exc.py
  - testable_claims:
      - applies_when: docstring (or empty)
      - surface_signals: ["{ClassName} raised"]
      - affects_compilation_phase: "dynamo"
      - verification_source: "pytorch@SHA:torch/_dynamo/exc.py:LINE"

Reproducibility:
  - Pinned input: pytorch HEAD SHA captured at runtime, recorded in provenance
  - Output is sorted by id → byte-identical reruns

Run:
    python -m extractors.pytorch_source.exc_classes
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from extractors.common import write_canonical_json  # noqa: E402
from extractors.common.base import Extractor  # noqa: E402
from extractors.common.provenance import git_commit_iso, git_head_sha  # noqa: E402
from extractors.pytorch_source._root import find_pytorch_root  # noqa: E402


def _camel_to_snake(name: str) -> str:
    """CamelCase → snake_case, idempotent on already-snake names."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _docstring_first_line(node: ast.ClassDef) -> str:
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    return doc.strip().splitlines()[0].strip()


def _base_class(node: ast.ClassDef) -> Optional[str]:
    if not node.bases:
        return None
    b = node.bases[0]
    if isinstance(b, ast.Name):
        return b.id
    if isinstance(b, ast.Attribute):
        # e.g., RuntimeError → "RuntimeError"
        return b.attr
    return ast.unparse(b)


class ExcClassesExtractor(Extractor):
    extractor_id = "pytorch_source.exc_classes"
    extractor_version = "1.0.0"
    output_path = "extractors/pytorch_source/output/symptoms_from_exc.json"

    def __init__(self, pytorch_root: Optional[Path] = None) -> None:
        self.pytorch_root = find_pytorch_root(pytorch_root)
        self.exc_path = self.pytorch_root / "torch" / "_dynamo" / "exc.py"
        if not self.exc_path.exists():
            raise FileNotFoundError(self.exc_path)
        self._head_sha = git_head_sha(self.pytorch_root) or "unknown"
        self._head_iso = git_commit_iso(self.pytorch_root, self._head_sha) or "unknown"

    def source_ref(self) -> str:
        return f"pytorch@{self._head_sha}:torch/_dynamo/exc.py"

    def extracted_at(self) -> str:
        # Source-state timestamp, not run wall-clock → byte-identical reruns.
        return self._head_iso

    def _walk_classes(self) -> list[tuple[ast.ClassDef, int]]:
        tree = ast.parse(self.exc_path.read_text(encoding="utf-8"))
        return [(n, n.lineno) for n in tree.body if isinstance(n, ast.ClassDef)]

    def _is_dynamo_exception(self, classes: list[tuple[ast.ClassDef, int]]) -> set[str]:
        """Return the set of class names that transitively inherit from TorchDynamoException
        (or are TorchDynamoException itself).

        Some classes inherit from RuntimeError/Exception directly (e.g.,
        FailOnRecompileLimitHit). We include only Dynamo-rooted exceptions to
        avoid pulling in unrelated helpers.
        """
        by_name = {n.name: n for n, _ in classes}
        in_set: set[str] = set()

        def visit(name: str) -> bool:
            if name in in_set:
                return True
            if name == "TorchDynamoException":
                in_set.add(name)
                return True
            node = by_name.get(name)
            if node is None:
                return False
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name and visit(base_name):
                    in_set.add(name)
                    return True
            return False

        for n, _ in classes:
            visit(n.name)
        return in_set

    def extract(self) -> list[dict]:
        classes = self._walk_classes()
        dynamo_set = self._is_dynamo_exception(classes)
        out: list[dict] = []
        for node, lineno in classes:
            if node.name not in dynamo_set:
                continue
            cname = node.name
            doc = _docstring_first_line(node)
            base = _base_class(node)
            entity = {
                "id": f"dynamo_{_camel_to_snake(cname)}",
                "name": f"torch._dynamo.exc.{cname}",
                "entity_type": "symptom",
                "description": doc,
                "base_class": base,
                "source_line": lineno,
                "visibility": "oss",
                "testable_claims": {
                    "applies_when": doc,
                    "surface_signals": [f"{cname} raised"],
                    "affects_compilation_phase": "dynamo",
                    "verification_source": f"pytorch@{self._head_sha}:torch/_dynamo/exc.py:{lineno}",
                },
            }
            out.append(entity)
        # Stable sort for byte-identical reruns
        out.sort(key=lambda e: e["id"])
        return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pytorch-root", type=Path, default=None)
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = p.parse_args()

    ex = ExcClassesExtractor(pytorch_root=args.pytorch_root)
    out_path = ex.run(args.repo_root)
    print(f"wrote {out_path}")
    print(f"  source: {ex.source_ref()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
