from __future__ import annotations
from typing import Mapping

Translations = Mapping[str, str]

_catalogs: dict[str, Translations] = {
    "en": {
        "welcome": "Welcome to pmd_clever_note_bot!",
        "help": "Available: /start, /help, /tools, /note_add <text>, /note_list",
        "unknown_command": "Unknown command.",
        "notes_empty": "You have no notes yet.",
        "notes_saved": "Note saved.",
        "tools": "Tools: notes, food diary",
    },
    "ru": {
        "welcome": "Добро пожаловать в pmd_clever_note_bot!",
        "help": "Доступно: /start, /help, /tools, /note_add <текст>, /note_list",
        "unknown_command": "Неизвестная команда.",
        "notes_empty": "У вас пока нет заметок.",
        "notes_saved": "Заметка сохранена.",
        "tools": "Инструменты: заметки, дневник питания",
    },
}

def t(key: str, locale: str, fallback: str = "") -> str:
    return _catalogs.get(locale, {}).get(key) or _catalogs.get("en", {}).get(key) or fallback or key
