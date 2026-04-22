"""Base class for PT2 ontology extractors.

Each extractor:
1. Declares its identifier (`extractor_id`) — used in provenance stamping.
2. Resolves its inputs (declared in the source-domain INPUTS.md).
3. Produces a list of entity/edge dicts.
4. Writes them via canonical JSON I/O.
5. Re-runs deterministically: same inputs + same code → byte-identical output.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Dict, Any

from .io import write_canonical_json
from .provenance import Provenance, now_iso, stamp_entity


class Extractor(ABC):
    """Subclass and implement extract() and source_ref()."""

    #: Unique extractor identifier, e.g., "pytorch_source.exc_classes"
    extractor_id: str = ""

    #: Semantic version of the extractor logic. Bump when output format changes.
    extractor_version: str = "0.1.0"

    #: Output file path, relative to repo root.
    output_path: str = ""

    @abstractmethod
    def source_ref(self) -> str:
        """Return a stable reference to the source (e.g., 'pytorch@SHA:path' or 'url@fetched_at')."""

    @abstractmethod
    def extract(self) -> List[Dict[str, Any]]:
        """Return the list of extracted entity dicts (without provenance — base class adds it)."""

    def extracted_at(self) -> str:
        """Timestamp recorded in provenance.

        Default is wall-clock now; source-tree extractors should override to
        return the source commit timestamp so reruns are byte-identical.
        """
        return now_iso()

    def stamp(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply provenance to every entity."""
        prov = Provenance(
            extracted_by=f"{self.extractor_id}@{self.extractor_version}",
            extracted_from=self.source_ref(),
            extracted_at=self.extracted_at(),
        )
        return [stamp_entity(e, prov) for e in entities]

    def run(self, repo_root: Path) -> Path:
        """End-to-end: extract → stamp → write canonical JSON."""
        repo_root = Path(repo_root)
        entities = self.extract()
        stamped = self.stamp(entities)
        out = repo_root / self.output_path
        write_canonical_json(out, stamped)
        return out

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.extractor_id}@{self.extractor_version}>"
