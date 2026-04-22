"""Extract `unimplemented(...)` call sites under torch/_dynamo/ → cause entities.

`unimplemented(gb_type=..., context=..., explanation=..., hints=...)`
(defined in torch/_dynamo/exc.py) is the canonical helper Dynamo uses to
emit a graph break. Its `gb_type` is the short, context-free identifier
that joins to the public graph-break catalog
(https://meta-pytorch.org/compile-graph-break-site/). `explanation` is
the user-facing reason; `hints` is the user-facing fix list.

Each call site is a candidate cause entity:
  - id: `dynamo_cause_<gb_type_slug>` (preferred, when gb_type is a literal)
        or `dynamo_cause_<rel_path_slug>_L<line>` as fallback
  - name: gb_type literal, or "<rel_path>:<line>"
  - description: explanation literal (joined if multi-line)
  - hints: list of literal hint strings
  - gb_type: the catalog key (None if non-literal at the call site)
  - source_location: "torch/_dynamo/.../<file>:<line>"
  - testable_claims:
      - triggering_pattern: explanation
      - surface_message: explanation (Dynamo emits this verbatim in the GB msg)
      - code_signal: gb_type (matchable against logs)
      - verification_source: pytorch@SHA:path:line

When multiple call sites share the same literal gb_type, we keep them
separate (their explanations / hints sometimes diverge slightly) — dedup
is the consumer's job via the gb_type field.

Reproducibility:
  - Pinned input: pytorch HEAD SHA (recorded in provenance)
  - Files walked in sorted-path order; output sorted by id

Run:
    python -m extractors.pytorch_source.unsupported_calls
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

from extractors.common.base import Extractor  # noqa: E402
from extractors.common.provenance import git_commit_iso, git_head_sha  # noqa: E402
from extractors.pytorch_source._root import find_pytorch_root  # noqa: E402

_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")


def _slug(s: str) -> str:
    return _SLUG_RE.sub("_", s).strip("_").lower()


def _literal_or_none(node: ast.AST):
    """Return ast.literal_eval(node) or None if not a literal."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def _hints_literal(node: ast.AST) -> Optional[list[str]]:
    """Extract literal hint strings.

    The hints arg is often `[*graph_break_hints.SUPPORTABLE]` (Starred Name) —
    these reference module-level constants we don't follow. In that case we
    return the source text as a single-element list so the consumer at least
    knows which constant set was referenced.
    """
    if isinstance(node, ast.List):
        out: list[str] = []
        for elt in node.elts:
            v = _literal_or_none(elt)
            if isinstance(v, str):
                out.append(v)
            elif isinstance(elt, ast.Starred):
                # *graph_break_hints.X → record as "ref:graph_break_hints.X"
                try:
                    out.append(f"ref:{ast.unparse(elt.value)}")
                except Exception:
                    pass
            else:
                # other expressions → keep source text
                try:
                    out.append(f"expr:{ast.unparse(elt)}")
                except Exception:
                    pass
        return out
    return None


def _is_unimplemented_call(node: ast.AST) -> bool:
    """True if `node` is a Call to a function named `unimplemented`."""
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id == "unimplemented"
    if isinstance(fn, ast.Attribute):
        return fn.attr == "unimplemented"
    return False


def _kwarg(call: ast.Call, name: str) -> Optional[ast.AST]:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


class UnsupportedCallsExtractor(Extractor):
    extractor_id = "pytorch_source.unsupported_calls"
    extractor_version = "1.0.0"
    output_path = "extractors/pytorch_source/output/causes_from_unimplemented.json"

    def __init__(self, pytorch_root: Optional[Path] = None) -> None:
        self.pytorch_root = find_pytorch_root(pytorch_root)
        self.dynamo_root = self.pytorch_root / "torch" / "_dynamo"
        if not self.dynamo_root.exists():
            raise FileNotFoundError(self.dynamo_root)
        self._head_sha = git_head_sha(self.pytorch_root) or "unknown"
        self._head_iso = git_commit_iso(self.pytorch_root, self._head_sha) or "unknown"

    def source_ref(self) -> str:
        return f"pytorch@{self._head_sha}:torch/_dynamo/**/*.py"

    def extracted_at(self) -> str:
        return self._head_iso

    def _iter_files(self) -> list[Path]:
        # Sorted for deterministic walk.
        return sorted(self.dynamo_root.rglob("*.py"))

    def _walk_file(self, path: Path) -> list[dict]:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            return []
        rel = path.relative_to(self.pytorch_root).as_posix()
        out: list[dict] = []
        for node in ast.walk(tree):
            if not _is_unimplemented_call(node):
                continue
            # Skip the definition site itself (where unimplemented is *called* from
            # inside its own body) — exc.py is the only such file.
            if rel.endswith("torch/_dynamo/exc.py"):
                continue
            gb_type_node = _kwarg(node, "gb_type")
            explanation_node = _kwarg(node, "explanation")
            hints_node = _kwarg(node, "hints")
            context_node = _kwarg(node, "context")

            gb_type = _literal_or_none(gb_type_node) if gb_type_node else None
            explanation = _literal_or_none(explanation_node) if explanation_node else None
            hints = _hints_literal(hints_node) if hints_node else None
            context_repr = None
            if context_node is not None:
                ctx_lit = _literal_or_none(context_node)
                context_repr = ctx_lit if isinstance(ctx_lit, str) else (
                    f"expr:{ast.unparse(context_node)}" if context_node else None
                )

            lineno = node.lineno
            if isinstance(gb_type, str) and gb_type:
                eid = f"dynamo_cause_{_slug(gb_type)}"
                ename = gb_type
            else:
                eid = f"dynamo_cause_{_slug(rel)}_l{lineno}"
                ename = f"{rel}:{lineno}"

            entity = {
                "id": eid,
                "name": ename,
                "entity_type": "cause",
                "description": explanation if isinstance(explanation, str) else "",
                "gb_type": gb_type if isinstance(gb_type, str) else None,
                "hints": hints,
                "context_repr": context_repr,
                "source_location": f"{rel}:{lineno}",
                "visibility": "oss",
                "testable_claims": {
                    "triggering_pattern": explanation if isinstance(explanation, str) else "",
                    "surface_message": explanation if isinstance(explanation, str) else "",
                    "code_signal": gb_type if isinstance(gb_type, str) else None,
                    "verification_source": f"pytorch@{self._head_sha}:{rel}:{lineno}",
                },
            }
            out.append(entity)
        return out

    def extract(self) -> list[dict]:
        all_out: list[dict] = []
        seen_ids: set[str] = set()
        # Disambiguate duplicate IDs (same gb_type at multiple sites): suffix _2, _3, ...
        for path in self._iter_files():
            for entity in self._walk_file(path):
                base = entity["id"]
                eid = base
                n = 2
                while eid in seen_ids:
                    eid = f"{base}_{n}"
                    n += 1
                entity["id"] = eid
                seen_ids.add(eid)
                all_out.append(entity)
        all_out.sort(key=lambda e: e["id"])
        return all_out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pytorch-root", type=Path, default=None)
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = p.parse_args()

    ex = UnsupportedCallsExtractor(pytorch_root=args.pytorch_root)
    out_path = ex.run(args.repo_root)
    print(f"wrote {out_path}")
    print(f"  source: {ex.source_ref()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
