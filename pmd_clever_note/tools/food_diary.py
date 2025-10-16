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
            builder.add(InlineKeyboardButton(text="🔙 Back to Main", callback_data="fd_main"))
            builder.adjust(1, 1)  # 1 button per row
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

    async def _edit_records_menu(self, user_id: int, locale: str, offset: int = 0) -> tuple[str, InlineKeyboardMarkup]:
        """Show edit records menu with pagination."""
        records = await self._get_records(user_id)
        
        if not records:
            text = "📝 No records to edit."
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="🔙 Back to Records", callback_data="fd_records"))
            return text, builder.as_markup()
        
        # Show 5 records starting from offset
        start_idx = offset
        end_idx = min(offset + 5, len(records))
        display_records = records[start_idx:end_idx]
        
        text = f"✏️ Edit Records ({start_idx + 1}-{end_idx} of {len(records)})\n\nSelect a record to edit:"
        
        builder = InlineKeyboardBuilder()
        
        # Add record buttons
        for i, record in enumerate(display_records, start=start_idx):
            record_time = record.get('datetime_utc', record.get('timestamp', ''))
            record_text = record.get('record', record.get('text', ''))
            button_text = f"{i+1}. {record_time[:16]} - {record_text[:30]}"
            builder.add(InlineKeyboardButton(
                text=button_text,
                callback_data=f"fd_select_record_{record['id']}"
            ))
        
        # Pagination buttons
        if offset > 0:
            builder.add(InlineKeyboardButton(text="⬆️ Previous", callback_data=f"fd_edit_records_{offset-5}"))
        
        if end_idx < len(records):
            builder.add(InlineKeyboardButton(text="⬇️ Next", callback_data=f"fd_edit_records_{offset+5}"))
        
        # Back button
        builder.add(InlineKeyboardButton(text="🔙 Back to Records", callback_data="fd_records"))
        
        builder.adjust(1, 2, 1)  # 1 per row for records, 2 for pagination, 1 for back
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
        """Handle text input and move to hunger before selection."""
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
        
        # Update state with text and move to hunger before
        self._creation_states[user_id] = RecordCreationState(
            user_id=user_id,
            step="hunger_before",
            datetime_utc=state.datetime_utc,
            record_text=text.strip(),
            hunger_before=None,
            hunger_after=None
        )
        
        # Show hunger before selection
        return await self._show_hunger_scale(user_id, "before", locale)

    async def _show_hunger_scale(self, user_id: int, hunger_type: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show 10-level hunger scale with buttons."""
        hunger_labels = {
            1: "1 - Extremely hungry",
            2: "2 - Very hungry", 
            3: "3 - Hungry",
            4: "4 - Slightly hungry",
            5: "5 - Neutral",
            6: "6 - Slightly satisfied",
            7: "7 - Satisfied",
            8: "8 - Very satisfied",
            9: "9 - Full",
            10: "10 - Extremely full"
        }
        
        step_name = "before" if hunger_type == "before" else "after"
        text = f"🍽️ Hunger Level {step_name.title()}\n\nHow hungry were you {step_name} eating?\n\nSelect your hunger level:"
        
        builder = InlineKeyboardBuilder()
        
        # Add hunger level buttons (2 per row)
        for level in range(1, 11):
            builder.add(InlineKeyboardButton(
                text=hunger_labels[level],
                callback_data=f"fd_hunger_{hunger_type}_{level}"
            ))
        
        # Add Skip and Back buttons
        builder.add(InlineKeyboardButton(text="⏭️ Skip", callback_data=f"fd_hunger_{hunger_type}_skip"))
        builder.add(InlineKeyboardButton(text="🔙 Back", callback_data="fd_hunger_back"))
        
        builder.adjust(2, 2, 2, 2, 2, 1, 1)  # 2 per row for hunger levels, then 1 each for skip/back
        return text, builder.as_markup()

    async def handle_hunger_selection(self, user_id: int, hunger_type: str, level: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Handle hunger level selection."""
        state = self._creation_states.get(user_id)
        if not state:
            return "❌ Error: No active record creation.", None
        
        if level == "skip":
            hunger_value = None
        else:
            try:
                hunger_value = int(level)
            except ValueError:
                return "❌ Invalid hunger level.", None
        
        # Update state with hunger level
        if hunger_type == "before":
            new_state = RecordCreationState(
                user_id=user_id,
                step="hunger_after",
                datetime_utc=state.datetime_utc,
                record_text=state.record_text,
                hunger_before=hunger_value,
                hunger_after=None
            )
        else:  # after
            new_state = RecordCreationState(
                user_id=user_id,
                step="complete",
                datetime_utc=state.datetime_utc,
                record_text=state.record_text,
                hunger_before=state.hunger_before,
                hunger_after=hunger_value
            )
        
        self._creation_states[user_id] = new_state
        
        if hunger_type == "before":
            # Move to hunger after
            return await self._show_hunger_scale(user_id, "after", locale)
        else:
            # Save the complete record
            return await self._save_complete_record(user_id, locale)

    async def _save_complete_record(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Save the complete record and show confirmation."""
        state = self._creation_states.get(user_id)
        if not state:
            return "❌ Error: No active record creation.", None
        
        # Save the record
        record_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        record = {
            "id": record_id,
            "datetime_utc": state.datetime_utc,
            "record": state.record_text,
            "hunger_before": state.hunger_before,
            "hunger_after": state.hunger_after,
            "picture": None
        }
        
        await self.storage.write_jsonl(user_id, "food_diary/records.jsonl", [record])
        
        # Clear the creation state
        if user_id in self._creation_states:
            del self._creation_states[user_id]
        
        # Show confirmation message
        hunger_info = ""
        if state.hunger_before is not None and state.hunger_after is not None:
            hunger_info = f"\n🍽️ Hunger: {state.hunger_before}/10 → {state.hunger_after}/10"
        elif state.hunger_before is not None:
            hunger_info = f"\n🍽️ Hunger Before: {state.hunger_before}/10"
        elif state.hunger_after is not None:
            hunger_info = f"\n🍽️ Hunger After: {state.hunger_after}/10"
        
        text = f"✅ Record Added Successfully!\n\n📝 {state.record_text}{hunger_info}\n\n⏰ {state.datetime_utc[:16]}\n\nWhat would you like to do next?"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="➕ Add Another Record", callback_data="fd_add"))
        builder.add(InlineKeyboardButton(text="📝 View Records", callback_data="fd_records"))
        builder.add(InlineKeyboardButton(text="🏠 Main Menu", callback_data="fd_main"))
        builder.adjust(1, 1, 1)
        
        return text, builder.as_markup()

    async def handle_hunger_back(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Handle back navigation from hunger selection."""
        state = self._creation_states.get(user_id)
        if not state:
            return "❌ Error: No active record creation.", None
        
        if state.step == "hunger_before":
            # Go back to text input
            text = f"📝 What did you eat?\n\n⏰ Time: {state.datetime_utc[:16]}\n\nType your food record (any text):"
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="❌ Cancel", callback_data="fd_cancel_add"))
            return text, builder.as_markup()
        elif state.step == "hunger_after":
            # Go back to hunger before
            return await self._show_hunger_scale(user_id, "before", locale)
        else:
            return "❌ Error: Invalid back navigation.", None

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


    async def _show_record_details(self, user_id: int, record_id: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show individual record with edit/remove options."""
        records = await self._get_records(user_id)
        record = next((r for r in records if r['id'] == record_id), None)
        
        if not record:
            return "❌ Record not found.", None
        
        # Format record display
        record_time = record.get('datetime_utc', record.get('timestamp', ''))
        record_text = record.get('record', record.get('text', ''))
        hunger_before = record.get('hunger_before')
        hunger_after = record.get('hunger_after')
        
        text = "📝 Record Details\n\n"
        text += f"⏰ Time: {record_time[:16]}\n"
        text += f"🍽️ Food: {record_text}\n"
        
        if hunger_before is not None:
            text += f"🍽️ Hunger Before: {hunger_before}/10\n"
        if hunger_after is not None:
            text += f"🍽️ Hunger After: {hunger_after}/10\n"
        
        builder = InlineKeyboardBuilder()
        
        # Action buttons
        builder.add(InlineKeyboardButton(text="✏️ Edit Record", callback_data=f"fd_edit_record_{record_id}"))
        builder.add(InlineKeyboardButton(text="🗑️ Remove Record", callback_data=f"fd_remove_record_{record_id}"))
        
        # Navigation buttons
        records = await self._get_records(user_id)
        current_index = next((i for i, r in enumerate(records) if r['id'] == record_id), -1)
        
        if current_index > 0:
            prev_record = records[current_index - 1]
            builder.add(InlineKeyboardButton(text="⬅️ Previous Record", callback_data=f"fd_select_record_{prev_record['id']}"))
        
        if current_index < len(records) - 1:
            next_record = records[current_index + 1]
            builder.add(InlineKeyboardButton(text="➡️ Next Record", callback_data=f"fd_select_record_{next_record['id']}"))
        
        # Back button
        builder.add(InlineKeyboardButton(text="🔙 Back to Edit Menu", callback_data="fd_edit"))
        
        builder.adjust(2, 2, 1)  # 2 per row for actions, 2 for navigation, 1 for back
        return text, builder.as_markup()

    async def _show_remove_confirmation(self, user_id: int, record_id: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show record removal confirmation."""
        records = await self._get_records(user_id)
        record = next((r for r in records if r['id'] == record_id), None)
        
        if not record:
            return "❌ Record not found.", None
        
        record_text = record.get('record', record.get('text', ''))
        text = f"🗑️ Remove Record\n\nAre you sure you want to remove this record?\n\n\"{record_text[:50]}...\"\n\nThis action cannot be undone."
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="✅ Yes, Remove", callback_data=f"fd_confirm_remove_{record_id}"))
        builder.add(InlineKeyboardButton(text="❌ Cancel", callback_data=f"fd_select_record_{record_id}"))
        builder.adjust(1, 1)
        
        return text, builder.as_markup()

    async def _remove_record(self, user_id: int, record_id: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Remove a record from storage."""
        records = await self._get_records(user_id)
        updated_records = [r for r in records if r['id'] != record_id]
        
        # Clear the file and rewrite all remaining records
        await self.storage.write_text(user_id, "food_diary/records.jsonl", "")  # Clear file
        if updated_records:
            await self.storage.write_jsonl(user_id, "food_diary/records.jsonl", updated_records)
        
        return await self._edit_records_menu(user_id, locale, offset=0)

    async def _start_edit_record(self, user_id: int, record_id: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Start editing a record - show datetime selection with skip option."""
        records = await self._get_records(user_id)
        record = next((r for r in records if r['id'] == record_id), None)
        
        if not record:
            return "❌ Record not found.", None
        
        # Store the original record for editing
        self._creation_states[user_id] = RecordCreationState(
            user_id=user_id,
            step="datetime",
            datetime_utc=record.get('datetime_utc', record.get('timestamp', '')),
            record_text=record.get('record', record.get('text', '')),
            hunger_before=record.get('hunger_before'),
            hunger_after=record.get('hunger_after')
        )
        
        text = "✏️ Edit Record\n\n📅 Change the time? Select new time or skip:"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🕐 Now", callback_data="fd_time_now"))
        builder.add(InlineKeyboardButton(text="🕐 30 min ago", callback_data="fd_time_30m"))
        builder.add(InlineKeyboardButton(text="🕐 1 hour ago", callback_data="fd_time_1h"))
        builder.add(InlineKeyboardButton(text="🕐 2 hours ago", callback_data="fd_time_2h"))
        builder.add(InlineKeyboardButton(text="🕐 3 hours ago", callback_data="fd_time_3h"))
        builder.add(InlineKeyboardButton(text="🕐 4 hours ago", callback_data="fd_time_4h"))
        builder.add(InlineKeyboardButton(text="🕐 Custom Time", callback_data="fd_time_custom"))
        builder.add(InlineKeyboardButton(text="⏭️ Skip Time", callback_data="fd_skip_time"))
        builder.add(InlineKeyboardButton(text="🔙 Back", callback_data=f"fd_select_record_{record_id}"))
        
        builder.adjust(2, 2, 2, 1, 1, 1)  # 2 per row for time options, then 1 each for skip/back
        return text, builder.as_markup()


def build(storage: UserStorage) -> Tool:
    return _FoodDiaryTool(storage=storage)
