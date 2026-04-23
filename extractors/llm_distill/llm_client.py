"""Cached LLM client.

The cache IS the determinism mechanism. Every call goes through `call()`,
which computes a key from (input + prompt + model + temp + schema), checks
the on-disk cache, and either reads from disk (cache hit) or calls the LLM
and writes the response to disk (cache miss).

v0.1 — wired to llmvm (Meta's MetaGen gateway). Default model
claude-4-6-opus-genai, temperature 0.0 for reproducible runs.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from extractors.common.io import write_canonical_json

INPUT_PLACEHOLDER = "{{INPUT_TEXT}}"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class LLMRequest:
    """Everything that goes into the cache key. Anything that should NOT
    affect the cached response (caller metadata, request IDs, timestamps)
    must NOT be included here."""
    input_text: str
    prompt_template: str       # full text of the prompt template
    model: str                  # e.g., "claude-opus-4-7"
    temperature: float          # 0.0 for reproducible runs
    schema_json: str            # canonical JSON of the output schema

    def cache_key(self) -> str:
        """sha256 of canonical-serialized fields. Stable across processes."""
        canon = json.dumps({
            "input_text": self.input_text,
            "prompt_template": self.prompt_template,
            "model": self.model,
            "temperature": self.temperature,
            "schema_json": self.schema_json,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class CachedLLMClient:
    """Thin wrapper: check cache, call LLM on miss, write response back to cache.

    Cache layout: one JSON per call. Path = `<cache_dir>/<key>.json`.
    File contains: {request_summary, response, model_metadata}.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def call(self, req: LLMRequest) -> dict:
        key = req.cache_key()
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            with path.open() as f:
                return json.load(f)["response"]
        # cache miss — call LLM
        response = self._call_llm(req)
        write_canonical_json(path, {
            "cache_key": key,
            "request_summary": {
                "model": req.model,
                "temperature": req.temperature,
                "input_sha256": hashlib.sha256(req.input_text.encode()).hexdigest()[:12],
                "prompt_sha256": hashlib.sha256(req.prompt_template.encode()).hexdigest()[:12],
            },
            "response": response,
        })
        return response

    def _call_llm(self, req: LLMRequest):
        """Render the prompt, subprocess to llmvm, parse JSON.

        llmvm flags:
          -p   pipe mode (clean stdout, no streaming)
          -d   direct (skip llmvm runtime prompt — raw model)
          -m   model name (e.g., claude-4-6-opus-genai)
          -t   temperature
          -to  timeout seconds
        """
        if INPUT_PLACEHOLDER not in req.prompt_template:
            raise ValueError(
                f"prompt_template missing {INPUT_PLACEHOLDER} placeholder"
            )
        rendered = req.prompt_template.replace(INPUT_PLACEHOLDER, req.input_text)
        result = subprocess.run(
            [
                "llmvm",
                "-p", "-d",
                "-m", req.model,
                "-t", str(req.temperature),
                "-to", "300",
            ],
            input=rendered,
            capture_output=True,
            text=True,
            timeout=360,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"llmvm failed (rc={result.returncode}): {result.stderr[-500:]}"
            )
        raw = ANSI_RE.sub("", result.stdout).strip()
        # Some models occasionally wrap JSON in a fence even when told not to.
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"llmvm output not valid JSON: {e}\n--- output (last 500 chars) ---\n{raw[-500:]}"
            ) from e


def cache_status(cache_dir: Path) -> dict:
    """Quick stats: how many cached entries, total size."""
    cache_dir = Path(cache_dir)
    entries = list(cache_dir.glob("*.json"))
    return {
        "n_entries": len(entries),
        "total_bytes": sum(p.stat().st_size for p in entries),
    }
