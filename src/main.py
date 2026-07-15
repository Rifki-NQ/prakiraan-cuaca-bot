import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from pathlib import Path
from src.query import QueryBuilder
from src.service import AppService
from src.bot.router import CommandRouter
from src.bot.bot_state_handler import BotStateHandler
from src.bot.bot_handler import BotHandler


def setup_logging() -> None:
    # create folder for logs if not exists
    LOGS_FOLDER = Path("logs")
    LOGS_FOLDER.mkdir(exist_ok=True)

    # define loggers level
    LOGS_LEVEL = logging.DEBUG

    logging.basicConfig(
        level=LOGS_LEVEL,
        format="%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                filename=Path(LOGS_FOLDER / "bot_server.log"),
                maxBytes=10_000_000,
                backupCount=5,
                encoding="utf-8",
            ),
        ],
    )

    # supress loggers from dependencies
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def get_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


async def run_app(db_url: str, bot_token: str) -> None:
    query_builder = QueryBuilder()
    await query_builder.setup_db(db_url)
    app_service = AppService(query_builder)
    router = CommandRouter(app_service)
    bot_state_handler = BotStateHandler(query_builder)
    bot_handler = BotHandler(router, bot_state_handler)
    await bot_handler.run_bot(bot_token)


def main() -> None:
    setup_logging()
    load_dotenv()
    db_url = get_env("DATABASE_URL")
    bot_token = get_env("BOT_TOKEN")
    asyncio.run(run_app(db_url, bot_token))


if __name__ == "__main__":
    main()
