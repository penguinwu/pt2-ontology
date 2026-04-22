"""Extract Dynamo config flags from torch/_dynamo/config.py → config entities.

Each module-level assignment in config.py is a user-facing knob. The comment
block immediately preceding it is the canonical rationale (these are the
nearest thing PyTorch has to per-flag docstrings).

For each flag, we capture:
  - id: `dynamo_config_<flag_name>`
  - name: fully-qualified name (`torch._dynamo.config.<flag_name>`)
  - description: leading comment block (joined, stripped)
  - default_repr: source-text of the default value (preserved verbatim)
  - compile_ignored_category: parsed from `[@compile_ignored: X]` tag if present
  - deprecated: True if Config(deprecated=True, ...) or marked as such
  - deprecation_message: from Config(deprecation_message=...) when present
  - alias_of: target flag if Config(alias=...)
  - source_line: line number in config.py
  - testable_claims:
      - applies_when: rationale
      - default_value_repr: source text of the default
      - compile_ignored_category: tag value if present
      - verification_source: pytorch@SHA:torch/_dynamo/config.py:LINE

Skipped: type-only annotations, private names (leading underscore), and
non-assignment statements.

Reproducibility:
  - Pinned input: pytorch HEAD SHA (recorded in provenance)
  - Output is sorted by id → byte-identical reruns

Run:
    python -m extractors.pytorch_source.config_docstrings
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

_TAG_RE = re.compile(r"\[@compile_ignored:\s*([a-zA-Z0-9_]+)\s*\]")


def _leading_comment(lines: list[str], assign_lineno: int) -> str:
    """Return the comment block immediately above `assign_lineno` (1-indexed).

    Walk upward from the line above the assignment, collecting consecutive
    `#`-prefixed lines (allowing leading whitespace). Stop at a non-comment
    line or top of file. Return the comments joined with single newlines,
    with the leading `# ` stripped per line. Returns "" if no comment block.
    """
    out: list[str] = []
    i = assign_lineno - 2  # 0-indexed line above the assignment
    while i >= 0:
        line = lines[i].rstrip()
        stripped = line.lstrip()
        if stripped.startswith("#"):
            # strip "# " or "#" prefix; keep the rest verbatim
            text = stripped[1:]
            if text.startswith(" "):
                text = text[1:]
            out.append(text)
            i -= 1
            continue
        if stripped == "":
            # blank line breaks the block
            break
        break
    return "\n".join(reversed(out)).strip()


def _config_call_kwargs(node: ast.Call) -> dict:
    """Return a dict of literal-evaluable kwargs from a Config(...) call.

    Non-literal kwargs are skipped silently. Only kwarg names commonly used
    for ontology purposes are extracted (default, alias, deprecated,
    deprecation_message).
    """
    out: dict = {}
    if not isinstance(node, ast.Call):
        return out
    fn = node.func
    fn_name = (
        fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
    )
    if fn_name != "Config":
        return out
    for kw in node.keywords:
        if kw.arg is None:
            continue
        try:
            out[kw.arg] = ast.literal_eval(kw.value)
        except (ValueError, SyntaxError):
            # non-literal; record source text for human readers
            try:
                out[kw.arg] = ast.unparse(kw.value)
            except Exception:
                pass
    return out


def _value_repr(node: ast.AST) -> str:
    """Return source-text of an expression (for default values)."""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _flag_name(target: ast.AST) -> Optional[str]:
    """Return the flag name if `target` is a simple module-level Name."""
    if isinstance(target, ast.Name):
        return target.id
    return None


class ConfigDocstringsExtractor(Extractor):
    extractor_id = "pytorch_source.config_docstrings"
    extractor_version = "1.0.0"
    output_path = "extractors/pytorch_source/output/configs_from_dynamo_config.json"

    def __init__(self, pytorch_root: Optional[Path] = None) -> None:
        self.pytorch_root = find_pytorch_root(pytorch_root)
        self.config_path = self.pytorch_root / "torch" / "_dynamo" / "config.py"
        if not self.config_path.exists():
            raise FileNotFoundError(self.config_path)
        self._head_sha = git_head_sha(self.pytorch_root) or "unknown"
        self._head_iso = git_commit_iso(self.pytorch_root, self._head_sha) or "unknown"

    def source_ref(self) -> str:
        return f"pytorch@{self._head_sha}:torch/_dynamo/config.py"

    def extracted_at(self) -> str:
        return self._head_iso

    def _walk_assignments(self) -> list[tuple[str, int, ast.AST, dict]]:
        """Return list of (flag_name, lineno, value_node, config_kwargs).

        Walks only top-level assignments. Skips private names and non-Name
        targets (tuple unpacking, attribute assignments).
        """
        text = self.config_path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        results: list[tuple[str, int, ast.AST, dict]] = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if len(node.targets) != 1:
                    continue
                name = _flag_name(node.targets[0])
                if not name or name.startswith("_"):
                    continue
                kwargs = _config_call_kwargs(node.value) if isinstance(node.value, ast.Call) else {}
                results.append((name, node.lineno, node.value, kwargs))
            elif isinstance(node, ast.AnnAssign):
                name = _flag_name(node.target)
                if not name or name.startswith("_"):
                    continue
                if node.value is None:
                    # bare annotation, not a flag
                    continue
                kwargs = _config_call_kwargs(node.value) if isinstance(node.value, ast.Call) else {}
                results.append((name, node.lineno, node.value, kwargs))
        return results

    def extract(self) -> list[dict]:
        text = self.config_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        out: list[dict] = []
        for name, lineno, value_node, kwargs in self._walk_assignments():
            comment = _leading_comment(lines, lineno)
            tag_match = _TAG_RE.search(comment) if comment else None
            tag = tag_match.group(1) if tag_match else None
            # Strip the inline tag from the description for cleaner display
            description = _TAG_RE.sub("", comment).strip() if comment else ""
            default_repr = _value_repr(value_node)
            alias_of = kwargs.get("alias")
            deprecated = bool(kwargs.get("deprecated")) or "deprecated" in description.lower()[:80]
            deprecation_message = kwargs.get("deprecation_message")

            entity = {
                "id": f"dynamo_config_{name}",
                "name": f"torch._dynamo.config.{name}",
                "entity_type": "config",
                "description": description,
                "default_repr": default_repr,
                "compile_ignored_category": tag,
                "alias_of": alias_of,
                "deprecated": deprecated,
                "deprecation_message": deprecation_message,
                "source_line": lineno,
                "visibility": "oss",
                "testable_claims": {
                    "applies_when": description,
                    "default_value_repr": default_repr,
                    "compile_ignored_category": tag,
                    "verification_source": (
                        f"pytorch@{self._head_sha}:torch/_dynamo/config.py:{lineno}"
                    ),
                },
            }
            out.append(entity)
        out.sort(key=lambda e: e["id"])
        return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pytorch-root", type=Path, default=None)
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = p.parse_args()

    ex = ConfigDocstringsExtractor(pytorch_root=args.pytorch_root)
    out_path = ex.run(args.repo_root)
    print(f"wrote {out_path}")
    print(f"  source: {ex.source_ref()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
