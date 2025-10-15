from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ToolMeta:
    name: str
    description: str
    commands: Sequence[str]


class Tool(Protocol):
    meta: ToolMeta
    async def handle(self, user_id: int, command: str, args: str, locale: str) -> str: ...
