"""Resolve the PyTorch source root.

Default: ~/projects/pytorch. Falls back to Meta-internal mirrors if that
doesn't exist. Override with $PT2_ONTOLOGY_PYTORCH_ROOT.
"""
import os
from pathlib import Path
from typing import Optional


_FALLBACK_ROOTS = [
    Path.home() / "projects" / "pytorch",
    Path.home() / "fbsource" / "fbcode" / "caffe2",
]


def find_pytorch_root(override: Optional[Path] = None) -> Path:
    """Return the first existing PyTorch source root, or raise."""
    candidates = []
    if override is not None:
        candidates.append(Path(override))
    env = os.environ.get("PT2_ONTOLOGY_PYTORCH_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.extend(_FALLBACK_ROOTS)

    for c in candidates:
        if c.exists():
            return c

    raise FileNotFoundError(
        f"No PyTorch source root found. Tried: {[str(c) for c in candidates]}. "
        "Set $PT2_ONTOLOGY_PYTORCH_ROOT or pass --pytorch-root."
    )
