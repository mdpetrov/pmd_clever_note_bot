from __future__ import annotations
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .i18n import t
from .tools.base import Tool

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
    
    @router.callback_query(lambda c: c.data == "food_diary")
    async def food_diary_main(callback: types.CallbackQuery) -> None:
        locale = _get_locale_from_callback(callback, default_locale)
        text, keyboard = await food_diary_tool._show_main_menu(locale)
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    
    @router.callback_query(lambda c: c.data == "fd_records")
    async def food_diary_records(callback: types.CallbackQuery) -> None:
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


def register_food_diary_text_handler(router: Router, food_diary_tool: Tool, default_locale: str) -> None:
    """Register text message handler for food diary record creation."""
    
    @router.message()
    async def handle_text_input(message: types.Message) -> None:
        # Check if user is in record creation mode
        user_id = message.from_user.id if message.from_user else 0
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
        else:
            # Not in record creation mode, ignore the message
            pass


def _get_locale_from_callback(callback: types.CallbackQuery, default_locale: str) -> str:
    """Extract locale from callback query."""
    return (callback.from_user.language_code or default_locale).split("-")[0] if callback.from_user else default_locale
