import asyncio
import logging
from collections.abc import Callable
from telegram import Bot, Update, MessageEntity
from telegram.request import HTTPXRequest
from telegram.error import TimedOut, RetryAfter, BadRequest, NetworkError
from src.models.enums import Commands
from src.models.contexts import BotUpdateContext
from src.models.protocols import (
    BotRespondHandlerProtocol,
    BotStateHandlerProtocol,
    BotRateLimiterProtocol,
    UserRateLimiterProtocol,
)
from src.exceptions import (
    BotHandlerError,
    EmptyCommandError,
    InvalidCommandError,
    NotCommandTypeError,
    SendMessageRetryExhaustedError,
)


logger = logging.getLogger(__name__)


class BotHandler:
    MAX_CONCURRENT_TASKS = 15
    CONNECTION_POOL_SIZE = MAX_CONCURRENT_TASKS + 2
    UPDATE_TIMEOUT = 30  # bot long polling value
    SEND_MESSAGE_TIMEOUT = 2  # 2 seconds before retry mechanism trigger
    SEND_MESSAGE_RETRY_ATTEMPT = 3  # max retry attempt
    SEND_MESSAGE_RETRY_DELAY = 0.5  # delay per retry attempt

    def __init__(
        self,
        respond_handler: BotRespondHandlerProtocol,
        bot_state: BotStateHandlerProtocol,
        bot_rate_limiter: BotRateLimiterProtocol,
        user_rate_limiter: UserRateLimiterProtocol,
    ) -> None:
        self.respond_handler = respond_handler
        self.bot_state = bot_state
        self.bot_rate_limiter = bot_rate_limiter
        self.user_rate_limiter = user_rate_limiter
        # self._background_tasks holds a reference for tasks that
        # run for indefinitely in the background
        self._background_tasks: set[asyncio.Task[None]] = set()
        # self._active_tasks holds a reference for tasks
        # that run then finish
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TASKS)

    async def run_bot(self, bot_token: str) -> None:
        """Run the bot, retry the long polling if timed out."""
        self._create_rate_limiter_timer_task()
        while True:
            try:
                logger.info("Bot long polling started")
                current_offset = await self.bot_state.get_offset(bot_token)
                await self._start_long_polling(bot_token, current_offset)
            except TimedOut:
                logger.warning("Bot long polling timed out, retrying")
                continue

    async def _start_long_polling(
        self, bot_token: str, current_offset: int | None
    ) -> None:
        """
        Start the bot long polling,
        persist the offset whenever get_updates return update objects.
        """
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
                    self._create_respond_to_update_task(bot, update)

    def _create_respond_to_update_task(self, bot: Bot, update: Update) -> None:
        """Create the task for _respond_to_update()"""
        task = asyncio.create_task(self._respond_to_update(bot, update))
        task.set_name(f"Task-{update.update_id}")
        self._active_tasks.add(task)
        chat_id = update.effective_chat.id if update.effective_chat else None
        task.add_done_callback(self._handle_task_completion(bot, chat_id))

    async def _respond_to_update(self, bot: Bot, update: Update) -> None:
        """
        Parse the update object then pass it into BotRespondHandler,
        after that, send the respond message with retry mechanism.
        """
        await self._semaphore.acquire()  # limit the concurrency
        update_context = self._parse_update(update)
        if update_context is None:
            logger.info("Skip responding to non Message context")
            return
        logger.info(
            f"chat_id: ({update_context.chat_id}), "
            f"command: ({update_context.command}), "
            f"command_value: ({update_context.command_value})"
        )
        respond_message = await self.respond_handler.parse_command(
            chat_id=update_context.chat_id,
            command=update_context.command,
            input_value=update_context.command_value,
        )
        await self._send_messsage_with_retry(
            bot, update_context.chat_id, respond_message
        )

    def _create_send_bot_error_message_task(
        self, bot: Bot, chat_id: int, err_message: str
    ) -> None:
        """Create the task for _send_error_message()."""
        task = asyncio.create_task(self._send_error_message(bot, chat_id, err_message))
        task.set_name(f"Error-Message-{chat_id}")
        self._active_tasks.add(task)
        task.add_done_callback(self._handle_task_completion(bot, chat_id))

    async def _send_error_message(
        self, bot: Bot, chat_id: int, err_message: str
    ) -> None:
        """Send an error message to user."""
        await self._semaphore.acquire()  # limit the concurrency
        await self._send_messsage_with_retry(bot, chat_id, err_message)

    async def _send_messsage_with_retry(
        self, bot: Bot, chat_id: int, message: str
    ) -> None:
        """
        Send a message with retry mechanism, the retry mechanism is triggered
        when the send_message method raised TimedOut error.
        """
        for attempt in range(self.SEND_MESSAGE_RETRY_ATTEMPT):
            try:
                await self.bot_rate_limiter.add()  # telagram rate limited prevention
                await self.user_rate_limiter.acquire(
                    chat_id
                )  # bot user spam prevention
                await bot.send_message(
                    chat_id,
                    message,
                    parse_mode="HTML",
                    read_timeout=self.SEND_MESSAGE_TIMEOUT,
                )
                return
            except TimedOut:
                await asyncio.sleep(self.SEND_MESSAGE_RETRY_DELAY)
                logger.debug(
                    f"send_message timed out, chat_id: {chat_id}, retry attempt: {attempt}"
                )
        raise SendMessageRetryExhaustedError(
            chat_id, self.SEND_MESSAGE_RETRY_ATTEMPT, message
        )

    def _handle_task_completion(
        self, bot: Bot, chat_id: int | None
    ) -> Callable[[asyncio.Task[None]], None]:
        """Called inside task.add_done_callback()"""

        def _cb(task: asyncio.Task[None]) -> None:
            """
            Logs the error if the task raised an error,
            send the error message to user if the error is BotHandlerError,
            finally, release a semaphore then discard the task from self.active_task.
            """
            try:
                task.result()
            except SendMessageRetryExhaustedError as e:
                # purposely not sending this error to user
                logger.error(e.message)
            except BotHandlerError as e:
                # send the errors under BotHandlerError to user
                logger.warning(e.message)
                if chat_id is None:
                    logger.info("Skip responding to non Chat context")
                else:
                    self._create_send_bot_error_message_task(bot, chat_id, e.message)
            except RetryAfter as e:
                logger.error(f"Rate limited, chat_id: {chat_id}, error: {repr(e)}")
            except BadRequest as e:
                logger.error(f"Bad request: chat_id: {chat_id}, error: {repr(e)}")
            except NetworkError as e:
                logger.error(f"Network error: chat_id: {chat_id}, error: {repr(e)}")
            except asyncio.CancelledError:
                logger.error("Task was cancelled")
            except Exception as e:
                logger.error(f"Unexpected error: {repr(e)}", exc_info=e)
            else:
                logger.debug(f"Task: {task.get_name()} finished successfully")
                return
            finally:
                self._semaphore.release()  # release one slot of concurrency
                self._active_tasks.discard(task)
            logger.debug(f"Task: {task.get_name()} finished with error")

        return _cb

    async def _get_offset_from_latest_update(self, bot_token: str, bot: Bot) -> int:
        """In case offset not found on db, get the latest one from Bot, then store it."""
        while True:
            logger.debug("Checking for latest update offset")
            updates = await bot.get_updates(offset=-1, timeout=self.UPDATE_TIMEOUT)
            if not updates:
                continue
            logger.debug(f"Latest update found: offset num ({updates[0].update_id})")
            current_offset = updates[-1].update_id + 1
            await self.bot_state.store_offset(bot_token, current_offset)
            return current_offset

    def _create_rate_limiter_timer_task(self) -> None:
        """Create the task for self.bot_rate_limiter.start_reset_timer()."""
        task = asyncio.create_task(self.bot_rate_limiter.start_reset_timer())
        task.set_name("Bot-Rate-Limiter-reset-timer")
        self._background_tasks.add(task)

    def _parse_update(self, update: Update) -> BotUpdateContext | None:
        """Parse the update object then convert it into BotUpdateContext."""
        if update.message is not None:
            chat_id = update.message.chat_id
            text = self._validate_text_is_not_none(update.message.text, chat_id).split()
            command = self._validate_first_text_is_command(
                update.message.entities, text[0], chat_id
            )
            try:
                if len(text) == 1:
                    # return only the /command if there is no value after it
                    return BotUpdateContext(chat_id, Commands(command))
                else:
                    # return the /command plus the values after it
                    command_value = " ".join(text[1:])
                    return BotUpdateContext(chat_id, Commands(command), command_value)
            except ValueError:
                raise InvalidCommandError(chat_id, command)
        return None

    def _validate_first_text_is_command(
        self, entities: tuple[MessageEntity, ...], text: str, chat_id: int
    ) -> str:
        """Raise error if entities does not contain a bot_command type."""
        for entity in entities:
            if entity.type == "bot_command":
                return text
        raise NotCommandTypeError(chat_id, text)

    def _validate_text_is_not_none(self, text: str | None, chat_id: int) -> str:
        """Raise error when the text is either None or empty string."""
        if text is None or not text:
            raise EmptyCommandError(chat_id)
        return text
