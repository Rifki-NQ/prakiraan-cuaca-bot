import asyncio
import logging
from collections.abc import AsyncIterable
from telegram import Bot, Update, MessageEntity
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
    EmptyUpdateMessageError,
)


logger = logging.getLogger(__name__)


class BotHandler:
    GET_UPDATE_FREQUENCY = 1
    UPDATE_TIMEOUT = 10

    def __init__(
        self, command_router: CommandRouterProtocol, bot_state: BotStateHandlerProtocol
    ) -> None:
        self.router = command_router
        self.bot_state = bot_state

    async def run_bot(self, bot_token: str) -> None:
        async with Bot(bot_token) as bot:
            current_offset = await self._handle_offset(bot_token, bot)
            while True:
                logger.info(f"Checking bot update - offset num: {current_offset}")
                updates = await bot.get_updates(
                    offset=current_offset, timeout=self.UPDATE_TIMEOUT
                )
                if updates:
                    current_offset += 1
                for update in updates:
                    logger.debug(f"Responding to update id: {update.update_id}")
                    try:
                        parsed_update = self._parse_update(update)
                    except BotHandlerError as e:
                        logger.error(e)
                        continue
                    forecasts = self.router.route_command(parsed_update.command)
                    await self._send_buffered_message(
                        bot, parsed_update.chat_id, forecasts
                    )
                await asyncio.sleep(self.GET_UPDATE_FREQUENCY)

    async def _handle_offset(self, bot_token: str, bot: Bot) -> int:
        bot_polling_state = await self.bot_state.get_offset(bot_token)
        if bot_polling_state is not None:
            return bot_polling_state.offset
        while True:
            logger.debug("Checking for latest update")
            updates = await bot.get_updates(offset=-1, timeout=self.UPDATE_TIMEOUT)
            if not updates:
                continue
            logger.debug(f"Latest update found: offset num ({updates[0].update_id})")
            return updates[0].update_id + 1

    async def _send_buffered_message(
        self, bot: Bot, chat_id: int, forecasts: AsyncIterable[ForecastModel]
    ) -> None:
        msg = await bot.send_message(chat_id, "Getting weather forecast...")
        buffer: list[str] = []
        async for forecast in forecasts:
            buffer.append(format_single_weather_forecast(forecast))
            new_text = "\n".join(buffer)
            await bot.edit_message_text(new_text, chat_id, msg.message_id)
            await asyncio.sleep(1)

    def _parse_update(self, update: Update) -> BotUpdateContext:
        if update.message is not None:
            chat_id = update.message.chat_id
            text = self._validate_text(update.message.text)
            self._validate_text_type(update.message.entities, text)
            try:
                return BotUpdateContext(chat_id, Commands(text))
            except ValueError:
                raise InvalidCommandError(text)
        raise EmptyUpdateMessageError

    def _validate_text_type(
        self, entities: tuple[MessageEntity, ...], text: str
    ) -> None:
        for entity in entities:
            if entity.type == "bot_command":
                return
        raise NotCommandTypeError(text)

    def _validate_text(self, text: str | None) -> str:
        if text is not None:
            return text
        raise EmptyCommandError()
