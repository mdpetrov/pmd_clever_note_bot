from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    bot_token: str
    data_dir: Path
    log_level: str
    locale_default: str

    @staticmethod
    def load() -> "Settings":
        # Load .env in dev if present; ignore errors to keep it simple
        if os.path.exists(".env"):
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except Exception:
                pass

        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise RuntimeError("BOT_TOKEN is required")

        data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        locale_default = os.getenv("LOCALE_DEFAULT", "en").lower()

        return Settings(
            bot_token=bot_token,
            data_dir=data_dir,
            log_level=log_level,
            locale_default=locale_default,
        )
