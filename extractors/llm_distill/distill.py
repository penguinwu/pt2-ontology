"""DistillExtractor — base class for LLM-distillation extractors.

Subclass per (source, prompt) pair. The base class handles:
- snapshot loading
- prompt + schema loading
- cache-backed LLM call
- schema validation
- write to ontology/distilled/

v0.0 SKELETON. Wires together the contract; does not yet call a real LLM
(see llm_client.py).
"""
from __future__ import annotations

import json
import sys
from abc import abstractmethod
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from extractors.common.base import Extractor  # noqa: E402
from extractors.common.io import read_json  # noqa: E402
from extractors.common.provenance import file_sha256  # noqa: E402
from extractors.llm_distill.llm_client import CachedLLMClient, LLMRequest  # noqa: E402
from extractors.llm_distill.validate import validate_against_schema  # noqa: E402


class DistillExtractor(Extractor):
    """Base for LLM-distillation extractors.

    Subclasses must declare:
      - extractor_id (e.g., "llm_distill.dynamo_chat_entities")
      - extractor_version
      - snapshot_path (frozen input)
      - prompt_path  (versioned prompt template)
      - schema_path  (output JSON schema)
      - output_path  (under ontology/distilled/)
    """

    snapshot_path: str
    prompt_path: str
    schema_path: str
    model: str = "claude-4-6-opus-genai"
    temperature: float = 0.0

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or REPO_ROOT)
        self.snapshot_file = self.repo_root / self.snapshot_path
        self.prompt_file = self.repo_root / self.prompt_path
        self.schema_file = self.repo_root / self.schema_path
        for p in (self.snapshot_file, self.prompt_file, self.schema_file):
            if not p.exists():
                raise FileNotFoundError(p)
        self._snapshot_sha12 = file_sha256(self.snapshot_file)[:12]
        self._prompt_sha12 = file_sha256(self.prompt_file)[:12]
        self._schema_sha12 = file_sha256(self.schema_file)[:12]
        self.cache = CachedLLMClient(
            self.repo_root / "extractors/llm_distill/cache"
        )

    def source_ref(self) -> str:
        return (
            f"snapshot@{self._snapshot_sha12}"
            f" + prompt@{self._prompt_sha12}"
            f" + schema@{self._schema_sha12}"
            f" + model={self.model}"
        )

    def extracted_at(self) -> str:
        """Stable across reruns: anchor to the snapshot's content hash, not
        wall-clock. Same inputs → same timestamp."""
        return f"snapshot:{self._snapshot_sha12}"

    def _format_for_llm(self, snapshot_text: str) -> str:
        """Hook: convert raw snapshot text into the form fed to the LLM.

        Default: pass through unchanged (works for plain-text snapshots).
        Subclasses override to e.g. flatten JSON into a readable transcript.
        Whatever this returns becomes part of the cache key, so determinism
        is required: same snapshot in → same string out.
        """
        return snapshot_text

    def extract(self) -> list[dict]:
        snapshot_text = self.snapshot_file.read_text()
        prompt_template = self.prompt_file.read_text()
        schema_json = self.schema_file.read_text()

        req = LLMRequest(
            input_text=self._format_for_llm(snapshot_text),
            prompt_template=prompt_template,
            model=self.model,
            temperature=self.temperature,
            schema_json=schema_json,
        )
        response = self.cache.call(req)

        # Validate against schema. Reject silently-bad outputs.
        validate_against_schema(response, json.loads(schema_json))

        # Stamp provenance, return.
        return self._stamp_distilled(response, req.cache_key())

    def _stamp_distilled(self, entries: list[dict], cache_key: str) -> list[dict]:
        """Add llm_distill-specific provenance to each entry."""
        for e in entries:
            e["source_type"] = "llm_distilled"
            e["manually_curated"] = False
            e["llm_provenance"] = {
                "model": self.model,
                "temperature": self.temperature,
                "cache_key": cache_key,
                "snapshot_sha12": self._snapshot_sha12,
                "prompt_sha12": self._prompt_sha12,
                "schema_sha12": self._schema_sha12,
            }
        return entries
