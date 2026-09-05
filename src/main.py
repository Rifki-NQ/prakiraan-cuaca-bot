import os
import asyncio
import logging
import time
from logging.handlers import RotatingFileHandler
import argparse
from dotenv import load_dotenv
from pathlib import Path
from src.queries.etl_query import ETLQuery
from src.queries.bot_query import BotQuery
from src.queries.sqlite_query import LocationFinder
from src.service import BotService
from src.bot.bot_respond_throttler import GlobalRespondThrottler, UserRespondThrottler
from src.bot.bot_state_handler import BotStateHandler
from src.bot.location_flow_handler import LocationFlowHandler
from src.bot.bot_respond_handler import BotRespondHandler
from src.bot.bot_handler import BotHandler


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

    etl_query = ETLQuery()
    bot_query = BotQuery()
    location_finder = LocationFinder()
    await etl_query.setup_etl_db(etl_db_url)
    await bot_query.setup_bot_db(bot_db_url)
    await location_finder.setup_local_db(local_db_url)
    if args.build_local_db:
        await location_finder.start_csv_to_local_db_transformation(
            Path("adm4_codes/jawa_barat.csv")
        )
    bot_service = BotService(etl_query, bot_query)
    bot_rate_limiter = GlobalRespondThrottler(limit=29, limit_reset_interval=1)
    user_rate_limiter = UserRespondThrottler(response_cooldown=1)
    bot_state_handler = BotStateHandler(bot_query)
    location_flow_handler = LocationFlowHandler(location_finder)
    bot_respond_handler = BotRespondHandler(bot_service, location_flow_handler)
    bot_handler = BotHandler(
        bot_respond_handler, bot_state_handler, bot_rate_limiter, user_rate_limiter
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
