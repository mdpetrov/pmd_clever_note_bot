from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Dict, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..storage import UserStorage
from ..i18n import t
from .base import Tool, ToolMeta


@dataclass(frozen=True)
class FoodRecord:
    id: str
    datetime_utc: str
    record: str
    hunger_before: Optional[int] = None
    hunger_after: Optional[int] = None
    picture: Optional[str] = None


@dataclass
class RecordCreationState:
    """Tracks the state of record creation process."""
    user_id: int
    step: str  # 'datetime', 'text', 'hunger_before', 'hunger_after'
    datetime_utc: Optional[str] = None
    record_text: Optional[str] = None
    hunger_before: Optional[int] = None
    hunger_after: Optional[int] = None


@dataclass(frozen=True)
class _FoodDiaryTool(Tool):
    storage: UserStorage
    # In-memory state for record creation (in production, use Redis or database)
    _creation_states: Dict[int, RecordCreationState] = None
    
    meta: ToolMeta = ToolMeta(
        name="food_diary",
        description="Food diary with records and photos",
        commands=("food_diary", "fd_records", "fd_add", "fd_edit", "fd_settings"),
    )
    
    def __post_init__(self):
        if self._creation_states is None:
            object.__setattr__(self, '_creation_states', {})

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
            # Use new record structure
            record_text = record.get('record', record.get('text', ''))
            record_time = record.get('datetime_utc', record.get('timestamp', ''))
            text += f"{i}. {record_time[:16]} - {record_text[:50]}\n"
        
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
        builder.add(InlineKeyboardButton(text="🔙 Back to Main", callback_data="fd_main"))
        
        builder.adjust(2, 2, 1)  # 2 buttons per row for pagination, then 2 for actions, then 1 for back
        return text, builder.as_markup()

    async def _add_record_prompt(self, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show datetime selection menu for new record."""
        text = "➕ Add Food Record\n\n📅 When did you eat? Select the time:"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🕐 Now", callback_data="fd_time_now"))
        builder.add(InlineKeyboardButton(text="🕐 30 min ago", callback_data="fd_time_30m"))
        builder.add(InlineKeyboardButton(text="🕐 1 hour ago", callback_data="fd_time_1h"))
        builder.add(InlineKeyboardButton(text="🕐 2 hours ago", callback_data="fd_time_2h"))
        builder.add(InlineKeyboardButton(text="🕐 3 hours ago", callback_data="fd_time_3h"))
        builder.add(InlineKeyboardButton(text="🕐 4 hours ago", callback_data="fd_time_4h"))
        builder.add(InlineKeyboardButton(text="🕐 Custom Time", callback_data="fd_time_custom"))
        builder.add(InlineKeyboardButton(text="🔙 Back to Records", callback_data="fd_records"))
        
        builder.adjust(2, 2, 2, 1, 1)  # 2 per row for time options, then 1 for custom, then 1 for back
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

    async def handle_time_selection(self, user_id: int, time_option: str, locale: str) -> tuple[str, InlineKeyboardMarkup | None]:
        """Handle datetime selection and move to text input."""
        now = datetime.utcnow()
        
        if time_option == "now":
            selected_time = now
        elif time_option == "30m":
            selected_time = now - timedelta(minutes=30)
        elif time_option == "1h":
            selected_time = now - timedelta(hours=1)
        elif time_option == "2h":
            selected_time = now - timedelta(hours=2)
        elif time_option == "3h":
            selected_time = now - timedelta(hours=3)
        elif time_option == "4h":
            selected_time = now - timedelta(hours=4)
        elif time_option == "custom":
            return await self._show_custom_time_input(user_id, locale)
        else:
            return "❌ Invalid time selection.", None
        
        # Store the selected time and move to text input
        self._creation_states[user_id] = RecordCreationState(
            user_id=user_id,
            step="text",
            datetime_utc=selected_time.isoformat() + "Z"
        )
        
        text = f"📝 What did you eat?\n\n⏰ Time: {selected_time.strftime('%Y-%m-%d %H:%M')}\n\nType your food record (any text):"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="❌ Cancel", callback_data="fd_cancel_add"))
        
        return text, builder.as_markup()

    async def _show_custom_time_input(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show custom time input with keyboard."""
        # Set state to wait for custom time input
        self._creation_states[user_id] = RecordCreationState(
            user_id=user_id,
            step="custom_time"
        )
        
        text = "🕐 Custom Time\n\nType the date and time in format:\nYYYY-MM-DD HH:MM\n\nExample: 2024-01-15 14:30"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="❌ Cancel", callback_data="fd_cancel_add"))
        
        return text, builder.as_markup()

    async def handle_custom_time_input(self, user_id: int, time_text: str, locale: str) -> tuple[str, InlineKeyboardMarkup | None]:
        """Parse custom time input and move to text input."""
        try:
            # Try to parse the custom time
            selected_time = datetime.strptime(time_text.strip(), "%Y-%m-%d %H:%M")
            
            # Store the selected time and move to text input
            self._creation_states[user_id] = RecordCreationState(
                user_id=user_id,
                step="text",
                datetime_utc=selected_time.isoformat() + "Z"
            )
            
            text = f"📝 What did you eat?\n\n⏰ Time: {selected_time.strftime('%Y-%m-%d %H:%M')}\n\nType your food record (any text):"
            
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="❌ Cancel", callback_data="fd_cancel_add"))
            
            return text, builder.as_markup()
            
        except ValueError:
            return "❌ Invalid time format. Please use YYYY-MM-DD HH:MM\n\nExample: 2024-01-15 14:30", None

    async def handle_text_input(self, user_id: int, text: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Handle text input and save the record."""
        if not text.strip():
            return "❌ Please enter what you ate.", None
        
        # Check if it's a command (starts with /)
        if text.strip().startswith('/'):
            # Abort record creation
            if user_id in self._creation_states:
                del self._creation_states[user_id]
            return "❌ Record creation cancelled. Command detected.", None
        
        # Get the creation state
        state = self._creation_states.get(user_id)
        if not state or not state.datetime_utc:
            return "❌ Error: No time selected. Please start over.", None
        
        # Save the record
        record_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        record = {
            "id": record_id,
            "datetime_utc": state.datetime_utc,
            "record": text.strip(),
            "hunger_before": None,
            "hunger_after": None,
            "picture": None
        }
        
        await self.storage.write_jsonl(user_id, "food_diary/records.jsonl", [record])
        
        # Clear the creation state
        if user_id in self._creation_states:
            del self._creation_states[user_id]
        
        # Return to main menu
        return await self._show_main_menu(locale)

    async def cancel_record_creation(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Cancel record creation and return to main menu."""
        if user_id in self._creation_states:
            del self._creation_states[user_id]
        return await self._show_main_menu(locale)

    async def add_record(self, user_id: int, text: str, photo_id: str | None = None) -> str:
        """Legacy method - kept for compatibility."""
        record_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        record = {
            "id": record_id,
            "datetime_utc": datetime.utcnow().isoformat() + "Z",
            "record": text,
            "hunger_before": None,
            "hunger_after": None,
            "picture": photo_id
        }
        
        await self.storage.write_jsonl(user_id, "food_diary/records.jsonl", [record])
        return f"✅ Record added: {text[:30]}..."


def build(storage: UserStorage) -> Tool:
    return _FoodDiaryTool(storage=storage)
