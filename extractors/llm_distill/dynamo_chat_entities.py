"""DynamoChatEntities — extract PT2 ontology entities from the Dynamo chat.

Source: internal Dynamo workstream chat (space ID held in extractors/llm_distill/INPUTS.md, gitignored)
Snapshot: extractors/llm_distill/snapshots/dynamo_chat_latest.json (symlink)
Prompt:   extractors/llm_distill/prompts/extract_entities_v1.md
Schema:   extractors/llm_distill/schemas/entities_v1.json

Run:
  python3 -m extractors.llm_distill.dynamo_chat_entities

Writes to: ontology/distilled/dynamo_chat_<YYYY_MM_DD>.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from extractors.common.io import write_canonical_json  # noqa: E402
from extractors.llm_distill.distill import DistillExtractor  # noqa: E402


class DynamoChatEntities(DistillExtractor):
    extractor_id = "llm_distill.dynamo_chat_entities"
    extractor_version = "v0.1"
    snapshot_path = "extractors/llm_distill/snapshots/dynamo_chat_latest.json"
    prompt_path = "extractors/llm_distill/prompts/extract_entities_v1.md"
    schema_path = "extractors/llm_distill/schemas/entities_v1.json"

    def _format_for_llm(self, snapshot_text: str) -> str:
        """Flatten the snapshot JSON into a chat-transcript string.

        One line per message:
          [<sender>] <body>           (top-level)
          [<sender>] (re) <body>      (thread reply)

        Threads are kept in chronological order (the snapshot is already
        sorted by creation_timestamp). Reply context is implicit but the
        is_thread_reply flag is surfaced via the (re) marker so the LLM
        can disambiguate "this fixes that" claims.
        """
        records = json.loads(snapshot_text)
        lines = []
        for r in records:
            sender = r.get("sender_name") or "unknown"
            body = (r.get("message_body") or "").strip()
            if not body:
                continue
            marker = "(re) " if r.get("is_thread_reply") else ""
            lines.append(f"[{sender}] {marker}{body}")
        return "\n".join(lines)


def main() -> int:
    ext = DynamoChatEntities()
    print(f"source_ref: {ext.source_ref()}", file=sys.stderr)
    entries = ext.extract()
    print(f"extracted {len(entries)} entries", file=sys.stderr)

    distilled_dir = ext.repo_root / "ontology/distilled"
    distilled_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    out_path = distilled_dir / f"dynamo_chat_{today}.json"
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
