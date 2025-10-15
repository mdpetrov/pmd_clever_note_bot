from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Iterable, List

from .utils import log_if_slow

logger = logging.getLogger("pmd_clever_note")

class UserStorage:
    # Human-readable per-user storage. Logs only potentially slow disk I/O.
    def __init__(self, base: Path) -> None:
        self.base = base
        (self.base / "users").mkdir(parents=True, exist_ok=True)

    def _u(self, user_id: int) -> Path:
        d = self.base / "users" / str(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    @log_if_slow()
    async def write_jsonl(self, user_id: int, rel: str, items: Iterable[dict[str, Any]]) -> None:
        p = self._u(user_id) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for obj in items:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        logger.debug("write_jsonl(%s) -> %s", user_id, p)

    @log_if_slow()
    async def read_jsonl(self, user_id: int, rel: str) -> List[dict[str, Any]]:
        p = self._u(user_id) / rel
        if not p.exists():
            return []
        out: list[dict[str, Any]] = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        logger.debug("read_jsonl(%s) <- %s (%d items)", user_id, p, len(out))
        return out

    @log_if_slow()
    async def write_text(self, user_id: int, rel: str, text: str) -> None:
        p = self._u(user_id) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        logger.debug("write_text(%s) -> %s (%d chars)", user_id, p, len(text))

    @log_if_slow()
    async def read_text(self, user_id: int, rel: str) -> str:
        p = self._u(user_id) / rel
        if not p.exists():
            return ""
        content = p.read_text(encoding="utf-8")
        logger.debug("read_text(%s) <- %s (%d chars)", user_id, p, len(content))
        return content
