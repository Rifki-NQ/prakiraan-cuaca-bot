import asyncio
import logging
from collections.abc import AsyncIterable
from telegram import Bot, Update, MessageEntity
from telegram.error import TimedOut
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
    UPDATE_TIMEOUT = 30

    def __init__(
        self, command_router: CommandRouterProtocol, bot_state: BotStateHandlerProtocol
    ) -> None:
        self.router = command_router
        self.bot_state = bot_state

    async def run_bot(self, bot_token: str) -> None:
        """Run the bot, retry the long polling if timed out."""
        current_offset = await self.bot_state.get_offset(bot_token)
        while True:
            try:
                logger.info("Bot long polling started")
                await self._start_long_polling(bot_token, current_offset)
            except TimedOut:
                logger.error("Bot long polling timed out, retrying")
                continue

    async def _start_long_polling(
        self, bot_token: str, current_offset: int | None
    ) -> None:
        """
        Start bot long polling,
        if offset not found on db, get latest one with bot.get_updates(offset=-1).
        """
        async with Bot(bot_token) as bot:
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
                    logger.debug(f"Responding to update id: {update.update_id}")
                    try:
                        parsed_update = self._parse_update(update)
                        if parsed_update is None:
                            logger.error("Skip responding empty update.message")
                            continue
                    except BotHandlerError as e:
                        logger.error(e)
                        await bot.send_message(e.chat_id, e.message)
                        continue
                    forecasts = self.router.route_command(parsed_update.command)
                    await self._send_buffered_forecasts(
                        bot, parsed_update.chat_id, forecasts
                    )

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
        msg = await bot.send_message(chat_id, "Getting weather forecast...")
        buffer: list[str] = []
        async for forecast in forecasts:
            buffer.append(format_single_weather_forecast(forecast))
            new_text = "\n".join(buffer)
            await bot.edit_message_text(new_text, chat_id, msg.message_id)
            await asyncio.sleep(1)

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
        self, entities: tuple[MessageEntity, ...], text: str,
        chat_id: int
    ) -> None:
        for entity in entities:
            if entity.type == "bot_command":
                return
        raise NotCommandTypeError(chat_id, text)

    def _validate_text(self, text: str | None, chat_id: int) -> str:
        if text is not None:
            return text
        raise EmptyCommandError(chat_id)
