from __future__ import annotations
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .i18n import t
from .tools.base import Tool
from .tools.food_diary import RecordCreationState

router = Router()


def _get_locale(msg: types.Message, default_locale: str) -> str:
    return (msg.from_user.language_code or default_locale).split("-")[0] if msg.from_user else default_locale


def register_common(router: Router, default_locale: str) -> None:
    @router.message(Command("start"))
    async def start(m: types.Message) -> None:
        locale = _get_locale(m, default_locale)
        text = t("welcome", locale)
        
        # Add food diary button
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🍽️ Food Diary", callback_data="food_diary"))
        builder.adjust(1)
        
        await m.answer(text, reply_markup=builder.as_markup())

    @router.message(Command("help"))
    async def help_(m: types.Message) -> None:
        await m.answer(t("help", _get_locale(m, default_locale)))


def register_tools(router: Router, tool: Tool, default_locale: str) -> None:
    for cmd in tool.meta.commands:
        @router.message(Command(cmd))
        async def _handler(m: types.Message, _cmd: str = cmd, _tool: Tool = tool) -> None:
            args = (m.text or "").split(" ", 1)
            arg_text = args[1] if len(args) > 1 else ""
            locale = _get_locale(m, default_locale)
            reply = await _tool.handle(user_id=m.from_user.id if m.from_user else 0, command=_cmd, args=arg_text, locale=locale)
            await m.answer(reply)

    @router.message(Command("tools"))
    async def tools_(m: types.Message) -> None:
        await m.answer(t("tools", _get_locale(m, default_locale)))


def register_food_diary_callbacks(router: Router, food_diary_tool: Tool, default_locale: str) -> None:
    """Register callback handlers for food diary tool."""
    
    def _set_user_info_if_needed(callback: types.CallbackQuery) -> None:
        """Set user info in storage if not already set."""
        if callback.from_user:
            user_id = callback.from_user.id
            username = callback.from_user.username
            first_name = callback.from_user.first_name
            food_diary_tool.storage.set_user_info(user_id, username, first_name)
    
    @router.callback_query(lambda c: c.data == "food_diary")
    async def food_diary_main(callback: types.CallbackQuery) -> None:
        _set_user_info_if_needed(callback)
        locale = _get_locale_from_callback(callback, default_locale)
        text, keyboard = await food_diary_tool._show_main_menu(locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    @router.callback_query(lambda c: c.data == "fd_records")
    async def food_diary_records(callback: types.CallbackQuery) -> None:
        _set_user_info_if_needed(callback)
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        text, keyboard = await food_diary_tool._show_records(user_id, locale, offset=0)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    @router.callback_query(lambda c: c.data and c.data.startswith("fd_records_"))
    async def food_diary_records_pagination(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        # Extract offset from callback data
        try:
            offset = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            offset = 0
            
        text, keyboard = await food_diary_tool._show_records(user_id, locale, offset=offset)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    @router.callback_query(lambda c: c.data == "fd_add")
    async def food_diary_add(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        text, keyboard = await food_diary_tool._add_record_prompt(locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    @router.callback_query(lambda c: c.data == "fd_edit")
    async def food_diary_edit(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        text, keyboard = await food_diary_tool._edit_records_menu(user_id, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    @router.callback_query(lambda c: c.data == "fd_settings")
    async def food_diary_settings(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        text, keyboard = await food_diary_tool._show_settings(user_id, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    @router.callback_query(lambda c: c.data == "fd_main")
    async def food_diary_back_to_main(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        text, keyboard = await food_diary_tool._show_main_menu(locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Time selection handlers
    @router.callback_query(lambda c: c.data and c.data.startswith("fd_time_"))
    async def food_diary_time_selection(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        time_option = callback.data.replace("fd_time_", "")
        text, keyboard = await food_diary_tool.handle_time_selection(user_id, time_option, locale)
        
        if keyboard:
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.edit_text(text)
        await callback.answer()
    
    # Cancel record creation
    @router.callback_query(lambda c: c.data == "fd_cancel_add")
    async def food_diary_cancel_add(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        text, keyboard = await food_diary_tool.cancel_record_creation(user_id, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Edit records pagination
    @router.callback_query(lambda c: c.data and c.data.startswith("fd_edit_records_"))
    async def food_diary_edit_pagination(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        try:
            offset = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            offset = 0
            
        text, keyboard = await food_diary_tool._edit_records_menu(user_id, locale, offset=offset)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Record selection
    @router.callback_query(lambda c: c.data and c.data.startswith("fd_select_record_"))
    async def food_diary_select_record(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        record_id = callback.data.replace("fd_select_record_", "")
        text, keyboard = await food_diary_tool._show_record_details(user_id, record_id, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Edit record
    @router.callback_query(lambda c: c.data and c.data.startswith("fd_edit_record_"))
    async def food_diary_edit_record(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        record_id = callback.data.replace("fd_edit_record_", "")
        text, keyboard = await food_diary_tool._start_edit_record(user_id, record_id, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Remove record confirmation
    @router.callback_query(lambda c: c.data and c.data.startswith("fd_remove_record_"))
    async def food_diary_remove_record(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        record_id = callback.data.replace("fd_remove_record_", "")
        text, keyboard = await food_diary_tool._show_remove_confirmation(user_id, record_id, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Confirm removal
    @router.callback_query(lambda c: c.data and c.data.startswith("fd_confirm_remove_"))
    async def food_diary_confirm_remove(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        record_id = callback.data.replace("fd_confirm_remove_", "")
        text, keyboard = await food_diary_tool._remove_record(user_id, record_id, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Skip time during edit
    @router.callback_query(lambda c: c.data == "fd_skip_time")
    async def food_diary_skip_time(callback: types.CallbackQuery) -> None:
        user_id = callback.from_user.id if callback.from_user else 0
        
        # Move to text editing
        state = food_diary_tool._creation_states.get(user_id)
        if state:
            food_diary_tool._creation_states[user_id] = RecordCreationState(
                user_id=user_id,
                step="text",
                datetime_utc=state.datetime_utc,
                record_text=state.record_text,
                hunger_before=state.hunger_before,
                hunger_after=state.hunger_after,
                editing_record_id=state.editing_record_id
            )
        
        # Get user timezone for time display
        user_timezone = await food_diary_tool._get_user_timezone(user_id)
        formatted_time = food_diary_tool._format_time_for_user(state.datetime_utc, user_timezone) if state else ''
        
        text = f"📝 Edit Food Description\n\n⏰ Time: {formatted_time}\nCurrent: {state.record_text if state else ''}\n\nType new description or skip:"
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⏭️ Skip Text", callback_data="fd_skip_text"))
        builder.add(InlineKeyboardButton(text="🔙 Back", callback_data="fd_edit_back"))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
    
    # Hunger selection handlers
    @router.callback_query(lambda c: c.data and c.data.startswith("fd_hunger_"))
    async def food_diary_hunger_selection(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        parts = callback.data.split("_")
        if len(parts) >= 4:
            hunger_type = parts[2]  # "before" or "after"
            level = parts[3]  # level number or "skip"
            
            if level == "back":
                text, keyboard = await food_diary_tool.handle_hunger_back(user_id, locale)
            else:
                text, keyboard = await food_diary_tool.handle_hunger_selection(user_id, hunger_type, level, locale)
            
            if keyboard:
                await callback.message.edit_text(text, reply_markup=keyboard)
            else:
                await callback.message.edit_text(text)
        await callback.answer()
    
    # Skip text during edit
    @router.callback_query(lambda c: c.data == "fd_skip_text")
    async def food_diary_skip_text(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        # Move to drink input
        state = food_diary_tool._creation_states.get(user_id)
        if state:
            food_diary_tool._creation_states[user_id] = RecordCreationState(
                user_id=user_id,
                step="drink",
                datetime_utc=state.datetime_utc,
                record_text=state.record_text,
                hunger_before=None,
                hunger_after=None,
                drink=state.drink,
                editing_record_id=state.editing_record_id
            )
        
        # Show drink input
        text, keyboard = await food_diary_tool._show_drink_input(user_id, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Skip drink
    @router.callback_query(lambda c: c.data == "fd_skip_drink")
    async def food_diary_skip_drink(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        # Move to hunger before selection
        state = food_diary_tool._creation_states.get(user_id)
        if state:
            food_diary_tool._creation_states[user_id] = RecordCreationState(
                user_id=user_id,
                step="hunger_before",
                datetime_utc=state.datetime_utc,
                record_text=state.record_text,
                hunger_before=None,
                hunger_after=None,
                drink=state.drink,
                editing_record_id=state.editing_record_id
            )
        
        # Show hunger before selection
        text, keyboard = await food_diary_tool._show_hunger_scale(user_id, "before", locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Back to text input
    @router.callback_query(lambda c: c.data == "fd_text_back")
    async def food_diary_text_back(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        # Move back to text input
        state = food_diary_tool._creation_states.get(user_id)
        if state:
            food_diary_tool._creation_states[user_id] = RecordCreationState(
                user_id=user_id,
                step="text",
                datetime_utc=state.datetime_utc,
                record_text=state.record_text,
                hunger_before=None,
                hunger_after=None,
                drink=state.drink,
                editing_record_id=state.editing_record_id
            )
        
        # Show text input prompt
        user_timezone = await food_diary_tool._get_user_timezone(user_id)
        formatted_time = food_diary_tool._format_time_for_user(state.datetime_utc, user_timezone)
        text = f"📝 What did you eat?\n\n⏰ Time: {formatted_time}\n\nType your food record (any text):"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="⏭️ Skip Text", callback_data="fd_skip_text"))
        builder.add(InlineKeyboardButton(text="❌ Cancel", callback_data="fd_cancel_add"))
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
    
    # Back during edit
    @router.callback_query(lambda c: c.data == "fd_edit_back")
    async def food_diary_edit_back(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        # Clear the creation state and return to edit menu
        if user_id in food_diary_tool._creation_states:
            del food_diary_tool._creation_states[user_id]
        
        text, keyboard = await food_diary_tool._edit_records_menu(user_id, locale, offset=0)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Timezone settings
    @router.callback_query(lambda c: c.data == "fd_timezone_settings")
    async def food_diary_timezone_settings(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        text, keyboard = await food_diary_tool._show_timezone_settings(user_id, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    # Set timezone
    @router.callback_query(lambda c: c.data and c.data.startswith("fd_set_timezone_"))
    async def food_diary_set_timezone(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        user_id = callback.from_user.id if callback.from_user else 0
        
        timezone_str = callback.data.replace("fd_set_timezone_", "")
        text, keyboard = await food_diary_tool._set_timezone(user_id, timezone_str, locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()


def register_food_diary_text_handler(router: Router, food_diary_tool: Tool, default_locale: str) -> None:
    """Register text message handler for food diary record creation."""
    
    def _set_user_info_if_needed(message: types.Message) -> None:
        """Set user info in storage if not already set."""
        if message.from_user:
            user_id = message.from_user.id
            username = message.from_user.username
            first_name = message.from_user.first_name
            food_diary_tool.storage.set_user_info(user_id, username, first_name)
    
    @router.message()
    async def handle_text_input(message: types.Message) -> None:
        # Check if user is in record creation mode
        user_id = message.from_user.id if message.from_user else 0
        _set_user_info_if_needed(message)
        state = food_diary_tool._creation_states.get(user_id)
        
        if state:
            locale = _get_locale(message, default_locale)
            text = message.text or ""
            
            if state.step == "custom_time":
                # Handle custom time input
                result_text, keyboard = await food_diary_tool.handle_custom_time_input(user_id, text, locale)
                if keyboard:
                    await message.answer(result_text, reply_markup=keyboard)
                else:
                    await message.answer(result_text)
            elif state.step == "text":
                # This is the food record text
                result_text, keyboard = await food_diary_tool.handle_text_input(user_id, text, locale)
                if keyboard:
                    await message.answer(result_text, reply_markup=keyboard)
                else:
                    await message.answer(result_text)
            elif state.step == "drink":
                # Handle drink input
                result_text, keyboard = await food_diary_tool.handle_drink_input(user_id, text, locale)
                if keyboard:
                    await message.answer(result_text, reply_markup=keyboard)
                else:
                    await message.answer(result_text)
        else:
            # Not in record creation mode, ignore the message
            pass


def _get_locale_from_callback(callback: types.CallbackQuery, default_locale: str) -> str:
    """Extract locale from callback query."""
    return (callback.from_user.language_code or default_locale).split("-")[0] if callback.from_user else default_locale
