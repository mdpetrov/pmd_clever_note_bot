from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..storage import UserStorage
from ..i18n import t
from .base import Tool, ToolMeta


@dataclass(frozen=True)
class FoodRecord:
    id: str
    timestamp: str
    text: str
    photo_id: str | None = None


@dataclass(frozen=True)
class _FoodDiaryTool(Tool):
    storage: UserStorage
    meta: ToolMeta = ToolMeta(
        name="food_diary",
        description="Food diary with records and photos",
        commands=("food_diary", "fd_records", "fd_add", "fd_edit", "fd_settings"),
    )

    async def handle(self, user_id: int, command: str, args: str, locale: str) -> str:
        if command == "food_diary":
            return await self._show_main_menu(locale)
        elif command == "fd_records":
            return await self._show_records(user_id, locale, offset=0)
        elif command == "fd_add":
            return await self._add_record_prompt(locale)
        elif command == "fd_edit":
            return await self._edit_records_menu(user_id, locale)
        elif command == "fd_settings":
            return await self._show_settings(user_id, locale)
        return t("unknown_command", locale)

    async def _show_main_menu(self, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show main food diary menu with Records and Settings buttons."""
        text = "🍽️ Food Diary\n\nChoose an option:"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="📝 Records", callback_data="fd_records"))
        builder.add(InlineKeyboardButton(text="⚙️ Settings", callback_data="fd_settings"))
        builder.adjust(1)
        
        return text, builder.as_markup()

    async def _show_records(self, user_id: int, locale: str, offset: int = 0) -> tuple[str, InlineKeyboardMarkup]:
        """Show 5 records with pagination buttons."""
        records = await self._get_records(user_id)
        
        if not records:
            text = "📝 No food records yet.\n\nAdd your first record!"
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="➕ Add Record", callback_data="fd_add"))
            return text, builder.as_markup()
        
        # Show 5 records starting from offset
        start_idx = offset
        end_idx = min(offset + 5, len(records))
        display_records = records[start_idx:end_idx]
        
        text = f"📝 Food Records ({start_idx + 1}-{end_idx} of {len(records)})\n\n"
        for i, record in enumerate(display_records, start=start_idx + 1):
            text += f"{i}. {record['timestamp'][:16]} - {record['text'][:50]}\n"
        
        # Build pagination buttons
        builder = InlineKeyboardBuilder()
        
        # Previous button (only if not at start)
        if offset > 0:
            builder.add(InlineKeyboardButton(text="⬆️ Previous", callback_data=f"fd_records_{offset-5}"))
        
        # Next button (only if more records exist)
        if end_idx < len(records):
            builder.add(InlineKeyboardButton(text="⬇️ Next", callback_data=f"fd_records_{offset+5}"))
        
        # Action buttons
        builder.add(InlineKeyboardButton(text="➕ Add Record", callback_data="fd_add"))
        builder.add(InlineKeyboardButton(text="✏️ Edit Records", callback_data="fd_edit"))
        
        builder.adjust(2, 2)  # 2 buttons per row for pagination, then 2 for actions
        return text, builder.as_markup()

    async def _add_record_prompt(self, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Prompt user to add a new record."""
        text = "➕ Add Food Record\n\nSend me a message with your food record. You can also attach a photo!"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🔙 Back to Records", callback_data="fd_records"))
        
        return text, builder.as_markup()

    async def _edit_records_menu(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show edit records menu."""
        records = await self._get_records(user_id)
        
        if not records:
            text = "📝 No records to edit."
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="🔙 Back", callback_data="fd_records"))
            return text, builder.as_markup()
        
        text = f"✏️ Edit Records\n\nFound {len(records)} records. Select one to edit:"
        
        builder = InlineKeyboardBuilder()
        for i, record in enumerate(records[:10]):  # Show max 10 for editing
            builder.add(InlineKeyboardButton(
                text=f"{i+1}. {record['timestamp'][:16]}", 
                callback_data=f"fd_edit_{record['id']}"
            ))
        
        builder.add(InlineKeyboardButton(text="🔙 Back", callback_data="fd_records"))
        builder.adjust(1)
        
        return text, builder.as_markup()

    async def _show_settings(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show food diary settings."""
        text = "⚙️ Food Diary Settings\n\nConfigure your food diary preferences."
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🔙 Back", callback_data="fd_main"))
        
        return text, builder.as_markup()

    async def _get_records(self, user_id: int) -> List[dict[str, Any]]:
        """Get all food records for a user."""
        return await self.storage.read_jsonl(user_id, "food_diary/records.jsonl")

    async def add_record(self, user_id: int, text: str, photo_id: str | None = None) -> str:
        """Add a new food record."""
        record_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        record = {
            "id": record_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "text": text,
            "photo_id": photo_id
        }
        
        await self.storage.write_jsonl(user_id, "food_diary/records.jsonl", [record])
        return f"✅ Record added: {text[:30]}..."


def build(storage: UserStorage) -> Tool:
    return _FoodDiaryTool(storage=storage)
