from __future__ import annotations
import asyncio
import logging
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from .settings import Settings
from .storage import UserStorage
from .tools import notes
from .handlers import router as base_router, register_common, register_tools


def _setup_logging(level: str) -> None:
    logger = logging.getLogger("pmd_clever_note")
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    fh = RotatingFileHandler("logs/app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(ch)
    logger.addHandler(fh)


def run() -> None:
    settings = Settings.load()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "users").mkdir(parents=True, exist_ok=True)
    (settings.data_dir.parent / "logs").mkdir(parents=True, exist_ok=True)

    _setup_logging(settings.log_level)
    logger = logging.getLogger("pmd_clever_note")
    logger.info("starting bot")

    storage = UserStorage(settings.data_dir)

    notes_tool = notes.build(storage)

    dp = Dispatcher()
    register_common(base_router, settings.locale_default)
    register_tools(base_router, notes_tool, settings.locale_default)
    dp.include_router(base_router)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))

    asyncio.run(_poll(bot, dp))


async def _poll(bot: Bot, dp: Dispatcher) -> None:
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
