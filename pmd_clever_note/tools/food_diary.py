from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    step: str  # 'datetime', 'text', 'hunger_before', 'hunger_after', 'drink'
    datetime_utc: Optional[str] = None
    record_text: Optional[str] = None
    hunger_before: Optional[int] = None
    hunger_after: Optional[int] = None
    drink: Optional[str] = None
    editing_record_id: Optional[str] = None  # ID of record being edited, None for new records


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
        user_timezone = await self._get_user_timezone(user_id)
        
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
            formatted_time = self._format_time_for_user(record_time, user_timezone)
            text += f"{i}. 🕐 {formatted_time} - {record_text[:50]}\n"
        
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
        user_timezone = await self._get_user_timezone(user_id)
        
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
            formatted_time = self._format_time_for_user(record_time, user_timezone)
            button_text = f"{i+1}. 🕐 {formatted_time} - {record_text[:30]}"
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
        user_timezone = await self._get_user_timezone(user_id)
        timezone_display = user_timezone if user_timezone else "UTC"
        
        text = f"⚙️ Food Diary Settings\n\nCurrent timezone: {timezone_display}\n\nConfigure your preferences:"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🌍 Timezone", callback_data="fd_timezone_settings"))
        builder.add(InlineKeyboardButton(text="🔙 Back", callback_data="fd_main"))
        builder.adjust(1)
        
        return text, builder.as_markup()

    async def _get_records(self, user_id: int) -> List[dict[str, Any]]:
        """Get all food records for a user."""
        return await self.storage.read_jsonl(user_id, "food_diary/records.jsonl")
    
    async def _get_user_timezone(self, user_id: int) -> str | None:
        """Get user's timezone setting."""
        try:
            timezone_str = await self.storage.read_text(user_id, "food_diary/timezone.txt")
            return timezone_str.strip() if timezone_str.strip() else None
        except:
            return None
    
    async def _set_user_timezone(self, user_id: int, timezone_str: str) -> None:
        """Set user's timezone."""
        await self.storage.write_text(user_id, "food_diary/timezone.txt", timezone_str)
    
    async def _show_timezone_settings(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show timezone selection menu."""
        current_timezone = await self._get_user_timezone(user_id)
        current_display = current_timezone if current_timezone else "UTC"
        
        text = f"🌍 Timezone Settings\n\nCurrent timezone: {current_display}\n\nSelect your timezone:"
        
        # Common timezones
        timezones = [
            ("UTC", "UTC"),
            ("Europe/London", "Europe/London (GMT/BST)"),
            ("Europe/Berlin", "Europe/Berlin (CET/CEST)"),
            ("Europe/Moscow", "Europe/Moscow (MSK)"),
            ("America/New_York", "America/New York (EST/EDT)"),
            ("America/Chicago", "America/Chicago (CST/CDT)"),
            ("America/Denver", "America/Denver (MST/MDT)"),
            ("America/Los_Angeles", "America/Los Angeles (PST/PDT)"),
            ("Asia/Tokyo", "Asia/Tokyo (JST)"),
            ("Asia/Shanghai", "Asia/Shanghai (CST)"),
            ("Asia/Dubai", "Asia/Dubai (GST)"),
            ("Australia/Sydney", "Australia/Sydney (AEST/AEDT)"),
        ]
        
        builder = InlineKeyboardBuilder()
        
        for tz_id, tz_display in timezones:
            builder.add(InlineKeyboardButton(
                text=f"{'✓' if tz_id == current_timezone else '○'} {tz_display}",
                callback_data=f"fd_set_timezone_{tz_id}"
            ))
        
        builder.add(InlineKeyboardButton(text="🔙 Back to Settings", callback_data="fd_settings"))
        builder.adjust(1)
        
        return text, builder.as_markup()
    
    async def _set_timezone(self, user_id: int, timezone_str: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Set user timezone and show confirmation."""
        await self._set_user_timezone(user_id, timezone_str)
        
        # Get timezone display name
        timezone_display = {
            "UTC": "UTC",
            "Europe/London": "London (GMT/BST)",
            "Europe/Paris": "Paris (CET/CEST)",
            "Europe/Berlin": "Berlin (CET/CEST)",
            "Europe/Moscow": "Moscow (MSK)",
            "America/New_York": "New York (EST/EDT)",
            "America/Chicago": "Chicago (CST/CDT)",
            "America/Denver": "Denver (MST/MDT)",
            "America/Los_Angeles": "Los Angeles (PST/PDT)",
            "Asia/Tokyo": "Tokyo (JST)",
            "Asia/Shanghai": "Shanghai (CST)",
            "Asia/Dubai": "Dubai (GST)",
            "Australia/Sydney": "Sydney (AEST/AEDT)",
        }.get(timezone_str, timezone_str)
        
        text = f"✅ Timezone Updated!\n\nYour timezone is now set to: {timezone_display}\n\nAll times will be displayed in your local timezone."
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🔙 Back to Settings", callback_data="fd_settings"))
        builder.adjust(1)
        
        return text, builder.as_markup()
    
    def _format_time_for_user(self, utc_time_str: str, user_timezone: str | None) -> str:
        """Convert UTC time string to user's timezone and format for display."""
        try:
            from zoneinfo import ZoneInfo
            # Parse UTC time - remove Z suffix and assume UTC
            clean_time = utc_time_str.replace('Z', '')
            utc_dt = datetime.fromisoformat(clean_time).replace(tzinfo=timezone.utc)
            
            if user_timezone:
                # Convert to user's timezone
                user_tz = ZoneInfo(user_timezone)
                local_dt = utc_dt.astimezone(user_tz)
                return local_dt.strftime('%Y-%m-%d %H:%M')
            else:
                # Default to UTC if no timezone set
                return utc_dt.strftime('%Y-%m-%d %H:%M UTC')
        except Exception as e:
            # Log warning and fallback to original string if conversion fails
            import logging
            logger = logging.getLogger("pmd_clever_note")
            logger.warning(f"Timezone conversion failed for '{utc_time_str}' with timezone '{user_timezone}': {e}")
            return utc_time_str[:16]

    async def handle_time_selection(self, user_id: int, time_option: str, locale: str) -> tuple[str, InlineKeyboardMarkup | None]:
        """Handle datetime selection and move to text input."""
        now = datetime.now(timezone.utc)
        user_timezone = await self._get_user_timezone(user_id)
        
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
            datetime_utc=selected_time.isoformat() + "Z",
            editing_record_id=None
        )
        
        # Format time for display in user's timezone
        formatted_time = self._format_time_for_user(selected_time.isoformat() + "Z", user_timezone)
        text = f"📝 What did you eat?\n\n⏰ Time: {formatted_time}\n\nType your food record (any text):"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⏭️ Skip Text", callback_data="fd_skip_text"))
        builder.add(InlineKeyboardButton(text="❌ Cancel", callback_data="fd_cancel_add"))
        builder.adjust(1)
        
        return text, builder.as_markup()

    async def _show_custom_time_input(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show custom time input with keyboard."""
        # Set state to wait for custom time input
        self._creation_states[user_id] = RecordCreationState(
            user_id=user_id,
            step="custom_time",
            editing_record_id=None
        )
        
        text = f"🕐 Custom Time\n\nType the date and time in format:\nYYYY-MM-DD HH:MM\n\nExample: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="❌ Cancel", callback_data="fd_cancel_add"))
        
        return text, builder.as_markup()

    async def handle_custom_time_input(self, user_id: int, time_text: str, locale: str) -> tuple[str, InlineKeyboardMarkup | None]:
        """Parse custom time input and move to text input."""
        try:
            # Try to parse the custom time
            selected_time = datetime.strptime(time_text.strip(), "%Y-%m-%d %H:%M")
            user_timezone = await self._get_user_timezone(user_id)
            
            # Convert from user's timezone to UTC for storage
            if user_timezone:
                from zoneinfo import ZoneInfo
                user_tz = ZoneInfo(user_timezone)
                # Assume the input time is in user's timezone
                local_dt = selected_time.replace(tzinfo=user_tz)
                utc_dt = local_dt.astimezone(timezone.utc)
            else:
                # If no timezone set, assume UTC
                utc_dt = selected_time.replace(tzinfo=timezone.utc)
            
            # Store the selected time and move to text input
            self._creation_states[user_id] = RecordCreationState(
                user_id=user_id,
                step="text",
                datetime_utc=utc_dt.isoformat() + "Z",
                editing_record_id=None
            )
            
            # Format time for display in user's timezone (should match what they entered)
            formatted_time = self._format_time_for_user(utc_dt.isoformat() + "Z", user_timezone)
            text = f"📝 What did you eat?\n\n⏰ Time: {formatted_time}\n\nType your food record (any text):"
            
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="⏭️ Skip Text", callback_data="fd_skip_text"))
            builder.add(InlineKeyboardButton(text="❌ Cancel", callback_data="fd_cancel_add"))
            builder.adjust(1)
            
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
        
        # Update state with text and move to drink input
        self._creation_states[user_id] = RecordCreationState(
            user_id=user_id,
            step="drink",
            datetime_utc=state.datetime_utc,
            record_text=text.strip(),
            hunger_before=None,
            hunger_after=None,
            drink=state.drink,
            editing_record_id=state.editing_record_id
        )
        
        # Show drink input
        return await self._show_drink_input(user_id, locale)

    async def _show_hunger_scale(self, user_id: int, hunger_type: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show 10-level hunger scale with buttons."""
        hunger_labels = {
            1: "😵 1 - Extremely hungry",
            2: "😫 2 - Very hungry", 
            3: "😖 3 - Hungry",
            4: "😐 4 - Slightly hungry",
            5: "😌 5 - Neutral",
            6: "🙂 6 - Slightly satisfied",
            7: "😊 7 - Satisfied",
            8: "😄 8 - Very satisfied",
            9: "🤤 9 - Full",
            10: "🤢 10 - Extremely full"
        }
        
        step_name = "before" if hunger_type == "before" else "after"
        step_emoji = "🍽️" if hunger_type == "before" else "😋"
        text = f"{step_emoji} Hunger Level {step_name.title()}\n\nHow hungry were you {step_name} eating?\n\nSelect your hunger level:"
        
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
                hunger_after=None,
                editing_record_id=state.editing_record_id
            )
        else:  # after
            new_state = RecordCreationState(
                user_id=user_id,
                step="complete",
                datetime_utc=state.datetime_utc,
                record_text=state.record_text,
                hunger_before=state.hunger_before,
                hunger_after=hunger_value,
                drink=state.drink,
                editing_record_id=state.editing_record_id
            )
        
        self._creation_states[user_id] = new_state
        
        if hunger_type == "before":
            # Move to hunger after
            return await self._show_hunger_scale(user_id, "after", locale)
        else:
            # Save the complete record
            return await self._save_complete_record(user_id, locale)

    async def _show_drink_input(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Show drink input prompt."""
        text = "🥤 What did you drink?\n\nType what you drank or skip:"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⏭️ Skip Drink", callback_data="fd_skip_drink"))
        builder.add(InlineKeyboardButton(text="🔙 Back", callback_data="fd_text_back"))
        builder.adjust(1)
        
        return text, builder.as_markup()

    async def handle_drink_input(self, user_id: int, drink_text: str, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Handle drink text input and move to hunger before selection."""
        state = self._creation_states.get(user_id)
        if not state:
            return "❌ Error: No active record creation.", None
        
        # Update state with drink text and move to hunger before
        self._creation_states[user_id] = RecordCreationState(
            user_id=user_id,
            step="hunger_before",
            datetime_utc=state.datetime_utc,
            record_text=state.record_text,
            hunger_before=None,
            hunger_after=None,
            drink=drink_text.strip(),
            editing_record_id=state.editing_record_id
        )
        
        # Show hunger before selection
        return await self._show_hunger_scale(user_id, "before", locale)

    async def _save_complete_record(self, user_id: int, locale: str) -> tuple[str, InlineKeyboardMarkup]:
        """Save the complete record and show confirmation."""
        state = self._creation_states.get(user_id)
        if not state:
            return "❌ Error: No active record creation.", None
        
        is_editing = state.editing_record_id is not None
        
        if is_editing:
            # Update existing record
            records = await self._get_records(user_id)
            record_index = next((i for i, r in enumerate(records) if r['id'] == state.editing_record_id), -1)
            
            if record_index == -1:
                return "❌ Error: Record to edit not found.", None
            
            # Update the existing record
            records[record_index].update({
                "datetime_utc": state.datetime_utc,
                "record": state.record_text,
                "hunger_before": state.hunger_before,
                "hunger_after": state.hunger_after,
                "drink": state.drink
            })
            
            # Clear the file and rewrite all records
            await self.storage.write_text(user_id, "food_diary/records.jsonl", "")  # Clear file
            await self.storage.write_jsonl(user_id, "food_diary/records.jsonl", records)
            
            action_text = "Record Updated Successfully!"
        else:
            # Create new record
            record_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            record = {
                "id": record_id,
                "datetime_utc": state.datetime_utc,
                "record": state.record_text,
                "hunger_before": state.hunger_before,
                "hunger_after": state.hunger_after,
                "drink": state.drink,
                "picture": None
            }
            
            await self.storage.write_jsonl(user_id, "food_diary/records.jsonl", [record])
            action_text = "Record Added Successfully!"
        
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
        
        drink_info = f"\n🥤 Drink: {state.drink}" if state.drink else ""
        
        # Format time for display in user's timezone
        user_timezone = await self._get_user_timezone(user_id)
        formatted_time = self._format_time_for_user(state.datetime_utc, user_timezone)
        text = f"✅ {action_text}\n\n📝 {state.record_text}{hunger_info}{drink_info}\n\n🕐 {formatted_time}\n\nWhat would you like to do next?"
        
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
            user_timezone = await self._get_user_timezone(user_id)
            formatted_time = self._format_time_for_user(state.datetime_utc, user_timezone)
            text = f"📝 What did you eat?\n\n⏰ Time: {formatted_time}\n\nType your food record (any text):"
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
        record_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        record = {
            "id": record_id,
            "datetime_utc": datetime.now(timezone.utc).isoformat() + "Z",
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
        user_timezone = await self._get_user_timezone(user_id)
        
        if not record:
            return "❌ Record not found.", None
        
        # Format record display
        record_time = record.get('datetime_utc', record.get('timestamp', ''))
        record_text = record.get('record', record.get('text', ''))
        hunger_before = record.get('hunger_before')
        hunger_after = record.get('hunger_after')
        drink = record.get('drink')
        formatted_time = self._format_time_for_user(record_time, user_timezone)
        
        text = "📝 Record Details\n\n"
        text += f"🕐 Time: {formatted_time}\n"
        text += f"🍽️ Food: {record_text}\n"
        
        if hunger_before is not None:
            text += f"🍽️ Hunger Before: {hunger_before}/10\n"
        if hunger_after is not None:
            text += f"🍽️ Hunger After: {hunger_after}/10\n"
        if drink:
            text += f"🥤 Drink: {drink}\n"
        
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
        user_timezone = await self._get_user_timezone(user_id)
        
        if not record:
            return "❌ Record not found.", None
        
        # Store the original record for editing
        self._creation_states[user_id] = RecordCreationState(
            user_id=user_id,
            step="datetime",
            datetime_utc=record.get('datetime_utc', record.get('timestamp', '')),
            record_text=record.get('record', record.get('text', '')),
            hunger_before=record.get('hunger_before'),
            hunger_after=record.get('hunger_after'),
            drink=record.get('drink'),
            editing_record_id=record_id
        )
        
        # Format current time for display
        current_time = record.get('datetime_utc', record.get('timestamp', ''))
        formatted_time = self._format_time_for_user(current_time, user_timezone)
        text = f"✏️ Edit Record\n\n📅 Current time: {formatted_time}\n\nChange the time? Select new time or skip:"
        
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
