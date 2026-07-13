import asyncio
import logging
from collections.abc import AsyncIterable, Callable
from telegram import Bot, Update, MessageEntity
from telegram.request import HTTPXRequest
from telegram.error import TimedOut, RetryAfter, NetworkError
from src.models.domain_model import ForecastModel
from src.models.commands import Commands
from src.models.contexts import BotUpdateContext
from src.models.protocols import CommandRouterProtocol, BotStateHandlerProtocol
from src.utils import format_single_weather_forecast
from src.exceptions import (
    BotHandlerError,
    EmptyCommandError,
    InvalidCommandError,
    NotCommandTypeError,
)


logger = logging.getLogger(__name__)


class BotHandler:
    MAX_CONCURENT_TASKS = 10
    CONNECTION_POOL_SIZE = MAX_CONCURENT_TASKS + 5  # add 5 more slots for error message
    UPDATE_TIMEOUT = 30
    BUFFERED_MESSAGE_DELAY = 1

    def __init__(
        self, command_router: CommandRouterProtocol, bot_state: BotStateHandlerProtocol
    ) -> None:
        self.router = command_router
        self.bot_state = bot_state
        self.semaphore = asyncio.Semaphore(self.MAX_CONCURENT_TASKS)
        self.active_tasks: set[asyncio.Task[None]] = set()

    async def run_bot(self, bot_token: str) -> None:
        """Run the bot, retry the long polling if timed out."""
        current_offset = await self.bot_state.get_offset(bot_token)
        while True:
            try:
                logger.info("Bot long polling started")
                await self._start_long_polling(bot_token, current_offset)
            except TimedOut:
                logger.warning("Bot long polling timed out, retrying")
                continue

    async def _start_long_polling(
        self, bot_token: str, current_offset: int | None
    ) -> None:
        """Start the bot long polling."""
        request = HTTPXRequest(
            connection_pool_size=self.CONNECTION_POOL_SIZE,
            pool_timeout=5,
            connect_timeout=5,
            read_timeout=self.UPDATE_TIMEOUT + 5,
        )
        async with Bot(bot_token, request=request) as bot:
            if current_offset is None:
                current_offset = await self._get_offset_from_latest_update(
                    bot_token, bot
                )
            while True:
                logger.info(f"Checking bot update - offset num: {current_offset}")
                updates = await bot.get_updates(
                    offset=current_offset, timeout=self.UPDATE_TIMEOUT
                )
                if updates:
                    current_offset = updates[-1].update_id + 1
                    await self.bot_state.store_offset(bot_token, current_offset)
                for update in updates:
                    if len(self.active_tasks) >= self.MAX_CONCURENT_TASKS:
                        logger.warning("Task limit reached, update will queue")
                        await self._wait_until_task_free(update.update_id)
                    task = asyncio.create_task(self._respond_to_update(bot, update))
                    self.active_tasks.add(task)
                    chat_id = (
                        update.effective_chat.id if update.effective_chat else None
                    )
                    task.add_done_callback(self._handle_task_completion(bot, chat_id))

    async def _respond_to_update(self, bot: Bot, update: Update) -> None:
        logger.debug(f"Responding to update id: {update.update_id}")
        parsed_update = self._parse_update(update)
        if parsed_update is None:
            logger.info("Skip responding to non Message context")
            return
        forecasts = self.router.route_command(parsed_update.command)
        async with self.semaphore:  # limit concurent _send_buffered_forecasts
            await self._send_buffered_forecasts(bot, parsed_update.chat_id, forecasts)

    async def _get_offset_from_latest_update(self, bot_token: str, bot: Bot) -> int:
        """In case offset not found on db, get the latest one from bot, then store it."""
        while True:
            logger.debug("Checking for latest update offset")
            updates = await bot.get_updates(offset=-1, timeout=self.UPDATE_TIMEOUT)
            if not updates:
                continue
            logger.debug(f"Latest update found: offset num ({updates[0].update_id})")
            current_offset = updates[-1].update_id + 1
            await self.bot_state.store_offset(bot_token, current_offset)
            return current_offset

    async def _send_buffered_forecasts(
        self, bot: Bot, chat_id: int, forecasts: AsyncIterable[ForecastModel]
    ) -> None:
        """Send buffered forecasts with edit_message_text for every forecast."""
        msg = await bot.send_message(
            chat_id,
            "Getting weather forecast...",
            pool_timeout=10,
            read_timeout=10,
            connect_timeout=10,
        )
        buffer: list[str] = []
        async for forecast in forecasts:
            buffer.append(format_single_weather_forecast(forecast))
            new_text = "\n".join(buffer)
            await bot.edit_message_text(
                new_text,
                chat_id,
                msg.message_id,
                pool_timeout=10,
                read_timeout=10,
                connect_timeout=10,
            )
            await asyncio.sleep(self.BUFFERED_MESSAGE_DELAY)

    def _handle_task_completion(
        self, bot: Bot, chat_id: int | None
    ) -> Callable[[asyncio.Task[None]], None]:
        """Called inside task.add_done_callback()"""

        def _cb(task: asyncio.Task[None]) -> None:
            """
            Logs the error if the task raised an error,
            send the error message to user if the error is BotHandlerError,
            finally, discard the task from self.active_task.
            """
            try:
                result = task.result()
                if result is None:
                    logger.info(f"Task: {task.get_name()} finished successfully")
                    return
            except BotHandlerError as e:
                logger.warning(e.message)
                if chat_id is None:
                    logger.info("Skip responding to non Chat context")
                else:
                    asyncio.create_task(bot.send_message(chat_id, e.message))
            except RetryAfter as e:
                logger.error(e.message)
            except NetworkError as e:
                logger.error(e.message)
            except asyncio.CancelledError:
                logger.error("Task was cancelled")
            finally:
                self.active_tasks.discard(task)
            logger.info(f"Task: {task.get_name()} finished with error")

        return _cb

    async def _wait_until_task_free(self, update_id: int) -> None:
        """Loop until there is free task slot."""
        loop_frequency = 1
        while True:
            logger.debug(f"In queue: update_id - {update_id}")
            if len(self.active_tasks) < self.MAX_CONCURENT_TASKS:
                break
            await asyncio.sleep(loop_frequency)

    def _parse_update(self, update: Update) -> BotUpdateContext | None:
        if update.message is not None:
            chat_id = update.message.chat_id
            text = self._validate_text(update.message.text, chat_id)
            self._validate_text_type(update.message.entities, text, chat_id)
            try:
                return BotUpdateContext(chat_id, Commands(text))
            except ValueError:
                raise InvalidCommandError(chat_id, text)
        return None

    def _validate_text_type(
        self, entities: tuple[MessageEntity, ...], text: str, chat_id: int
    ) -> None:
        for entity in entities:
            if entity.type == "bot_command":
                return
        raise NotCommandTypeError(chat_id, text)

    def _validate_text(self, text: str | None, chat_id: int) -> str:
        if text is not None:
            return text
        raise EmptyCommandError(chat_id)
