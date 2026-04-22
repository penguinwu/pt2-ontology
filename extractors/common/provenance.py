"""Provenance stamping for reproducible ontology extraction.

Every extracted entity records WHO extracted it (extractor + version),
WHERE it came from (source ref), and WHEN. This lets any reader trace
a fact back to its origin and re-run the extractor to verify.

Hand-curated fields (Beaver's audit findings, Peng's classifications)
are preserved across re-extractions via the manually_curated marker.
See REPRODUCIBILITY.md for the full contract.
"""
import hashlib
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class Provenance:
    """Per-entity provenance record.

    Attributes:
        extracted_by: extractor identifier "module.name@version" (e.g., "pytorch_source.exc_classes@1.0.0")
        extracted_from: source reference (e.g., "pytorch@d7d04823795:torch/_dynamo/exc.py:42")
        extracted_at: ISO 8601 UTC timestamp
        source_sha256: optional content hash of the source artifact at extraction time
    """
    extracted_by: str
    extracted_from: str
    extracted_at: str
    source_sha256: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def now_iso() -> str:
    """UTC timestamp, second precision (no microseconds → stable across reruns within 1s)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def file_sha256(path: Path) -> str:
    """SHA-256 of a file's bytes."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head_sha(repo_root: Path) -> Optional[str]:
    """Return the HEAD commit SHA of a git repo, or None if not a git repo."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def stamp_entity(entity: dict, prov: Provenance) -> dict:
    """Attach a provenance record to an entity dict (non-destructive copy).

    Provenance lives under entity["provenance"]. Existing fields are preserved.
    If the entity is marked manually_curated=True, provenance is recorded but
    extractor reruns will not overwrite hand-edited fields (caller's responsibility
    via the merge logic in REPRODUCIBILITY.md).
    """
    out = dict(entity)
    out["provenance"] = prov.to_dict()
    return out


def snapshot_source(source_path: Path, snapshot_dir: Path, label: str) -> Path:
    """Copy a source artifact into the extractor's snapshots/ for non-deterministic sources.

    Use for sources that mutate over time (web pages, GChat threads, GitHub issue bodies).
    Returns the snapshot path. Filename includes the source SHA-256 prefix for collision-free
    versioning.
    """
    source_path = Path(source_path)
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    sha_prefix = file_sha256(source_path)[:12]
    dest = snapshot_dir / f"{label}_{sha_prefix}{source_path.suffix}"
    if not dest.exists():
        dest.write_bytes(source_path.read_bytes())
    return dest
