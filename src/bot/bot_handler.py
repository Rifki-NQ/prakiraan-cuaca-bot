import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from telegram import Bot, Update
from telegram.error import TimedOut, RetryAfter, BadRequest, NetworkError
from src.models.enums import Commands
from src.models.contexts import BotUpdateContext
from src.models.protocols import (
    BotRespondHandlerProtocol,
    BotStateHandlerProtocol,
    GlobalRespondThrottlerProtocol,
    UserRespondThrottlerProtocol,
)
from src.exceptions import (
    BotHandlerError,
    EmptyMessageTextError,
    InvalidCommandError,
    NotCommandTypeError,
    SendMessageRetryExhaustedError,
)


logger = logging.getLogger(__name__)


class BotHandler:
    MAX_CONCURRENT_TASKS: int = 15
    POLLING_TIMEOUT: int = 30
    SEND_MESSAGE_TIMEOUT: float = 2  # 2 seconds before retry mechanism trigger
    SEND_MESSAGE_RETRY_ATTEMPT: int = 3  # max retry attempt
    SEND_MESSAGE_RETRY_DELAY: float = 0.5  # delay per retry attempt

    def __init__(
        self,
        respond_handler: BotRespondHandlerProtocol,
        bot_state: BotStateHandlerProtocol,
        global_throttler: GlobalRespondThrottlerProtocol,
        user_throttler: UserRespondThrottlerProtocol,
    ) -> None:
        self.respond_handler = respond_handler
        self.bot_state = bot_state
        self.global_throttler = global_throttler
        self.user_throttler = user_throttler
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TASKS)
        self._bot_is_running = False
        self._long_polling_is_running = False

    async def run_bot(self, bot_token: str) -> None:
        """Run the bot, retry the long polling if timed out."""
        if self._bot_is_running:
            logger.warning("Bot is already running, no need to run again")
            return
        logger.info("Bot started")
        self._bot_is_running = True
        self.global_throttler.start_reset_timer()
        self.user_throttler.start_delete_stale_data_cycle()
        try:
            while self._bot_is_running:
                try:
                    current_offset = await self.bot_state.get_offset(bot_token)
                    await self._start_polling_loop(bot_token, current_offset)
                except NetworkError as e:
                    logger.warning(f"Network error occured: {repr(e)}, retrying")
                    continue
        finally:
            self.stop_bot()

    def stop_bot(self) -> None:
        """
        Stop the bot by flipping both self._long_polling_is_running
        and self._bot_is_running to False.
        """
        if not self._bot_is_running:
            logger.warning("Bot is not running, no need to stop")
            return
        self._stop_polling_loop()
        self._bot_is_running = False
        logger.info("Bot stopped")

    def _stop_polling_loop(self) -> None:
        """
        Stop the bot long polling by flipping
        the self._long_polling_is_running to False.
        """
        if not self._long_polling_is_running:
            logger.warning("polling loop is not running, no need to stop")
            return
        self._long_polling_is_running = False
        logger.info("Long polling stopped")

    async def _start_polling_loop(
        self, bot_token: str, current_offset: int | None
    ) -> None:
        """
        Start the bot long polling loop,
        persist the offset whenever get_updates return update objects.
        """
        try:
            if self._long_polling_is_running:
                logger.warning("long polling already started, no need to start again")
                return
            async with Bot(bot_token) as bot:
                if current_offset is None:
                    # if current_offset does not exist in the db
                    # set it to -1 so it will only proceed the latest update
                    current_offset = -1
                # start the long polling loop
                self._long_polling_is_running = True
                logger.info("Bot long polling loop started")
                while self._long_polling_is_running:
                    current_offset = await self._poll_once(bot, current_offset)
                    await self.bot_state.store_offset(bot_token, current_offset)
        finally:
            self._stop_polling_loop()

    async def _poll_once(self, bot: Bot, current_offset: int) -> int:
        """Poll once then return the latest offset"""
        logger.info(f"Checking bot update - current offset: {current_offset}")
        updates = await bot.get_updates(
            offset=current_offset, timeout=self.POLLING_TIMEOUT
        )
        for update in updates:
            self._create_respond_to_update_task(bot, update)
        if updates:
            current_offset = updates[-1].update_id + 1
        return current_offset

    def _create_respond_to_update_task(self, bot: Bot, update: Update) -> None:
        """Create the task for _respond_to_update()"""
        task = asyncio.create_task(self._respond_to_update(bot, update))
        task.set_name(f"respond-for-{update.update_id}")
        self._active_tasks.add(task)
        chat_id = update.effective_chat.id if update.effective_chat else None
        task.add_done_callback(self._handle_task_completion(bot, chat_id))

    async def _respond_to_update(self, bot: Bot, update: Update) -> None:
        """
        Parse the update object then pass it into BotRespondHandler,
        after that, send the respond message with retry mechanism.
        """
        async with self._semaphore:
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
            await self._send_message_with_retry(
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
        async with self._semaphore:
            await self._send_message_with_retry(bot, chat_id, err_message)

    async def _send_message_with_retry(
        self, bot: Bot, chat_id: int, message: str
    ) -> None:
        """
        Send a message with retry mechanism, the retry mechanism is triggered
        when the send_message method raised TimedOut error.
        """
        for attempt in range(self.SEND_MESSAGE_RETRY_ATTEMPT):
            try:
                await (
                    self.global_throttler.acquire()  # telagram rate limited prevention
                )
                await self.user_throttler.acquire(  # bot user spam prevention
                    chat_id
                )
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
            except RetryAfter as e:
                retry_after = self._parse_retry_after(e.retry_after)
                logger.debug(f"rate limited, retry send message after: {retry_after}")
                await asyncio.sleep(retry_after)
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
                self._active_tasks.discard(task)
            logger.debug(f"Task: {task.get_name()} finished with error")

        return _cb

    def _parse_retry_after(self, retry_after: int | timedelta) -> float:
        if isinstance(retry_after, timedelta):
            return retry_after.total_seconds()
        else:
            return float(retry_after)

    def _parse_update(self, update: Update) -> BotUpdateContext | None:
        """Parse the update object, validate it,
        then convert it into BotUpdateContext."""
        if update.message is None:
            return None
        text = update.message.text
        chat_id = update.message.chat_id
        text = self._validate_text_is_not_none(text, chat_id)
        splitted_text = text.split()
        command_text = self._validate_first_text_is_command(splitted_text[0], chat_id)
        command_enum = self._validate_command_is_valid(command_text, chat_id)
        if len(splitted_text) == 1:
            # return only the /command if there is no value after it
            return BotUpdateContext(chat_id, command_enum)
        else:
            # return the /command plus the values after it
            command_value = " ".join(splitted_text[1:])
            return BotUpdateContext(chat_id, Commands(command_enum), command_value)

    def _validate_text_is_not_none(self, text: str | None, chat_id: int) -> str:
        """Raise EmptyTextError if passed text is None"""
        if text is None:
            raise EmptyMessageTextError(chat_id)
        return text

    def _validate_first_text_is_command(self, first_text: str, chat_id: int) -> str:
        """
        raise NotCommandTypeError if the passed first_text does not
        start with / or a slash.
        """
        if not first_text.startswith("/"):
            raise NotCommandTypeError(chat_id, first_text)
        return first_text

    def _validate_command_is_valid(self, command_text: str, chat_id: int) -> Commands:
        """
        Raise InvalidCommandError if the passed command_text
        is not known based on src.models.enums.Commands
        """
        try:
            return Commands(command_text)
        except ValueError:
            raise InvalidCommandError(chat_id, command_text)
