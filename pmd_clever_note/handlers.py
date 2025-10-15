from __future__ import annotations
from aiogram import Router, types
from aiogram.filters import Command

from .i18n import t
from .tools.base import Tool

router = Router()


def _get_locale(msg: types.Message, default_locale: str) -> str:
    return (msg.from_user.language_code or default_locale).split("-")[0] if msg.from_user else default_locale


def register_common(router: Router, default_locale: str) -> None:
    @router.message(Command("start"))
    async def start(m: types.Message) -> None:
        await m.answer(t("welcome", _get_locale(m, default_locale)))

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
