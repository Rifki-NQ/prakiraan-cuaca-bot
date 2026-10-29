import argparse
import asyncio
import logging
import os
import signal
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

from src.bot.bot_handler import BotHandler
from src.bot.bot_respond_handler import BotRespondHandler
from src.bot.bot_respond_throttler import GlobalRespondThrottler, UserRespondThrottler
from src.bot.bot_state_handler import BotStateHandler
from src.bot.bot_user_lock import BotUserLock
from src.bot.location_flow_handler import LocationFlowHandler
from src.queries.bot_query import BotQuery
from src.queries.etl_query import ETLQuery
from src.queries.sqlite_query import LocationFinder
from src.service import BotService

logger = logging.getLogger(__name__)


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
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def setup_signal_handler(stop_method: Callable[[], None]) -> None:
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop_method)
    loop.add_signal_handler(signal.SIGINT, stop_method)


def get_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prakiraan-cuaca-bot")
    parser.add_argument("--build-local-db", action="store_true", default=False)
    return parser


async def run_app(
    parser: argparse.ArgumentParser,
    etl_db_url: str,
    bot_db_url: str,
    local_db_url: str,
    bot_token: str,
) -> None:
    args = parser.parse_args()

    etl_query = ETLQuery(etl_db_url)
    bot_query = BotQuery(bot_db_url)
    location_finder = LocationFinder(local_db_url)
    bot_service = BotService(etl_query, bot_query)
    bot_rate_limiter = GlobalRespondThrottler(limit=29, limit_reset_interval=1)
    user_rate_limiter = UserRespondThrottler(response_cooldown=1)
    bot_user_lock = BotUserLock()
    bot_state_handler = BotStateHandler(bot_query)
    location_flow_handler = LocationFlowHandler(location_finder)
    bot_respond_handler = BotRespondHandler(bot_service, location_flow_handler)
    bot_handler = BotHandler(
        bot_respond_handler,
        bot_state_handler,
        bot_rate_limiter,
        user_rate_limiter,
        bot_user_lock,
    )
    setup_signal_handler(bot_handler.stop_bot)
    async with etl_query, bot_query, location_finder:
        if args.build_local_db:
            await location_finder.start_csv_to_local_db_transformation(
                Path("adm4_codes/jawa_barat.csv")
            )
        await bot_handler.run_bot(bot_token)


def main() -> None:
    setup_logging()
    load_dotenv()
    etl_db_url = get_env("ETL_DATABASE_URL")
    bot_db_url = get_env("BOT_DATABASE_URL")
    local_db_url = get_env("LOCAL_DATABASE_URL")
    bot_token = get_env("BOT_TOKEN")
    parser = build_parser()
    while True:
        try:
            asyncio.run(
                run_app(parser, etl_db_url, bot_db_url, local_db_url, bot_token)
            )
            break
        except OSError as e:
            logger.critical("OS-level error occured, retrying in 60s", exc_info=e)
            time.sleep(60)


if __name__ == "__main__":
    main()
