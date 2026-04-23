"""InductorChatEntities — extract PT2 ontology entities from the Inductor workstream weekly chat.

Source: internal Inductor workstream chat (space ID held in extractors/llm_distill/INPUTS.md, gitignored)
Snapshot: extractors/llm_distill/snapshots/inductor_chat_latest.json (symlink)
Prompt:   extractors/llm_distill/prompts/extract_entities_v1.md
Schema:   extractors/llm_distill/schemas/entities_v1.json

Run:
  python3 -m extractors.llm_distill.inductor_chat_entities

Writes to: ontology/distilled/inductor_chat_<YYYY_MM_DD>.json
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from extractors.common.io import write_canonical_json  # noqa: E402
from extractors.llm_distill.dynamo_chat_entities import DynamoChatEntities  # noqa: E402


class InductorChatEntities(DynamoChatEntities):
    extractor_id = "llm_distill.inductor_chat_entities"
    extractor_version = "v0.1"
    snapshot_path = "extractors/llm_distill/snapshots/inductor_chat_latest.json"


def main() -> int:
    ext = InductorChatEntities()
    print(f"source_ref: {ext.source_ref()}", file=sys.stderr)
    entries = ext.extract()
    print(f"extracted {len(entries)} entries", file=sys.stderr)

    distilled_dir = ext.repo_root / "ontology/distilled"
    distilled_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    out_path = distilled_dir / f"inductor_chat_{today}.json"
    write_canonical_json(out_path, {
        "extractor_id": ext.extractor_id,
        "extractor_version": ext.extractor_version,
        "source_ref": ext.source_ref(),
        "extracted_at": ext.extracted_at(),
        "entries": entries,
    })
    print(f"wrote {out_path}", file=sys.stderr)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
