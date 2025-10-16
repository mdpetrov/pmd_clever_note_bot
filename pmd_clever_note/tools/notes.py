from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..storage import UserStorage
from ..i18n import t
from .base import Tool, ToolMeta


@dataclass(frozen=True)
class _NotesTool(Tool):
    storage: UserStorage
    meta: ToolMeta = ToolMeta(
        name="notes",
        description="Simple text notes",
        commands=("note_add", "note_list"),
    )

    async def handle(self, user_id: int, command: str, args: str, locale: str) -> str:
        if command == "note_add":
            if not args.strip():
                return "Usage: /note_add <text>"
            item: dict[str, Any] = {"ts": datetime.now(timezone.utc).isoformat() + "Z", "text": args.strip()}
            await self.storage.write_jsonl(user_id, "notes/notes.jsonl", [item])
            return t("notes_saved", locale)
        if command == "note_list":
            notes = await self.storage.read_jsonl(user_id, "notes/notes.jsonl")
            if not notes:
                return t("notes_empty", locale)
            lines = [f"- {n['ts']}: {n['text']}" for n in notes[-20:]]
            return "\n".join(lines)
        return t("unknown_command", locale)


def build(storage: UserStorage) -> Tool:
    return _NotesTool(storage=storage)
