import logging
import asyncio
from typing import Literal, assert_never
from collections.abc import Awaitable, Callable
from src.bot import message_container
from src.bot.bot_router import route_command
from src.bot.forecast_responder import get_merged_forecasts
from src.models.protocols import (
    BotServiceProtocol,
    LocationFlowHandlerProtocol,
)
from src.models.domain_model import (
    LocationFlowResult,
    LocationFlowResultComplete,
    BotUserModel,
    BotUserStateModel,
)
from src.models.enums import Commands, BotAction, UserDataRestorationResult
from src.exceptions import DataIntegrityError

logger = logging.getLogger(__name__)


class BotRespondHandler:
    """Handles bot action routing and orchestration of bot services and bot flow handlers."""

    def __init__(
        self,
        bot_service: BotServiceProtocol,
        location_flow_handler: LocationFlowHandlerProtocol,
    ) -> None:
        self.bot_service = bot_service
        self.location_flow_handler = location_flow_handler

    async def parse_command(
        self, chat_id: int, command: Commands, input_value: str | None = None
    ) -> str:
        user_location_context = await self.bot_service.resolve_user_location_state(
            chat_id
        )
        bot_user_state = user_location_context.bot_user_state
        user_location_state = user_location_context.user_location_state  # enums object
        actions = route_command(command, user_location_state, input_value)
        messages: list[str] = []
        for action in actions:
            match action:
                case BotAction.SHOW_INTRO:
                    messages.append(message_container.SHOW_INTRO)
                case BotAction.SHOW_HELP:
                    messages.append(message_container.SHOW_HELP)
                case BotAction.SHOW_EXTRA_HELP:
                    messages.append(self._route_extra_help(input_value))
                case BotAction.ASK_CITY_OR_REGENCY:
                    messages.append(message_container.ASK_CITY_OR_REGENCY)
                case BotAction.ASK_SUBDISTRICT:
                    messages.append(
                        message_container.notify_to_choose_subdistrict(
                            await self.location_flow_handler.get_merged_subdistrict_list(
                                chat_id, bot_user_state
                            )
                        )
                    )
                case BotAction.ASK_VILLAGE:
                    messages.append(
                        message_container.notify_to_choose_village(
                            await self.location_flow_handler.get_merged_village_list(
                                chat_id, bot_user_state
                            )
                        )
                    )
                case BotAction.RECEIVE_INPUT_FOR_CITY_OR_REGENCY:
                    messages.append(
                        await self._handle_input_for_city_or_regency(
                            chat_id, input_value
                        )
                    )
                case BotAction.RECEIVE_INPUT_FOR_SUBDISTRICT:
                    messages.append(
                        await self._handle_input_for_subdistrict_and_village(
                            chat_id,
                            bot_user_state,
                            input_value,
                            self.location_flow_handler.handle_input_for_subdistrict,
                        )
                    )
                case BotAction.RECEIVE_INPUT_FOR_VILLAGE:
                    messages.append(
                        await self._handle_input_for_subdistrict_and_village(
                            chat_id,
                            bot_user_state,
                            input_value,
                            self.location_flow_handler.handle_input_for_village,
                        )
                    )
                case BotAction.TELLS_USER_NO_NEED_FOR_INPUT:
                    messages.append(message_container.TELLS_USER_NO_NEED_FOR_INPUT)
                case BotAction.TELLS_USER_TO_ADD_INPUT_VALUE:
                    messages.append(message_container.TELLS_USER_TO_ADD_INPUT_VALUE)
                case BotAction.TELLS_USER_TO_SET_LOCATION:
                    messages.append(message_container.TELLS_USER_TO_SET_LOCATION)
                case BotAction.TELLS_USER_TO_FINISH_SET_LOCATION:
                    messages.append(message_container.TELLS_USER_TO_FINISH_SET_LOCATION)
                case BotAction.SHOW_USER_CURRENT_LOCATION:
                    messages.append(
                        await self._handle_show_user_current_location(chat_id)
                    )
                case BotAction.SHOW_WELCOME_BACK_INTRO:
                    messages.append(message_container.SHOW_WELCOME_BACK_INTRO)
                case BotAction.SHOW_TODAY_FORECASTS:
                    messages.append(await self._get_forecast_message(chat_id, "today"))
                case BotAction.SHOW_TOMORROW_FORECASTS:
                    messages.append(
                        await self._get_forecast_message(chat_id, "tomorrow")
                    )
                case BotAction.TELLS_USER_NO_NEED_FOR_RESET:
                    messages.append(message_container.TELLS_USER_NO_NEED_FOR_RESET)
                case BotAction.RESET_USER_LOCATION:
                    messages.append(await self._reset_location(chat_id))
                case _:
                    assert_never(action)
        return "\n\n".join(messages)

    async def _handle_input_for_city_or_regency(
        self, chat_id: int, input_value: str | None
    ) -> str:
        try:
            flow_result = (
                await self.location_flow_handler.handle_input_for_city_or_regency(
                    chat_id, input_value
                )
            )
            await self._persist_location_result(chat_id, flow_result)
            return flow_result.message
        except DataIntegrityError as e:
            # reset the location state of this user
            await self._reset_user_state_data(e.chat_id)
            raise

    async def _handle_input_for_subdistrict_and_village(
        self,
        chat_id: int,
        user_state: BotUserStateModel | None,
        input_value: str | None,
        flow_handler: Callable[
            [int, BotUserStateModel | None, str | None],
            Awaitable[LocationFlowResult | LocationFlowResultComplete],
        ],
    ) -> str:
        try:
            flow_result = await flow_handler(chat_id, user_state, input_value)
            await self._persist_location_result(chat_id, flow_result)
            return flow_result.message
        except DataIntegrityError as e:
            # reset the location state of this user
            await self._reset_user_state_data(e.chat_id)
            raise

    async def _handle_show_user_current_location(self, chat_id: int) -> str:
        try:
            return await self._get_user_then_get_full_address(chat_id)
        except DataIntegrityError as e:
            # try restoring the user data by using user state data
            restore_result = await self._handle_when_user_data_is_missing(chat_id)
            if restore_result == UserDataRestorationResult.FAILED:
                # reset all data of this user
                # because at this point, the data for this user
                # is considered corrupted or missing
                await self._reset_user_state_data(e.chat_id, with_user_data=True)
                raise
            try:
                return await self._get_user_then_get_full_address(chat_id)
            except DataIntegrityError as e:
                await self._reset_user_state_data(e.chat_id, with_user_data=True)
                raise

    async def _get_user_then_get_full_address(self, chat_id: int) -> str:
        user_data = await self.bot_service.get_user(chat_id)
        return await self.location_flow_handler.get_full_address(chat_id, user_data)

    async def _get_forecast_message(
        self, chat_id: int, forecast_time: Literal["today", "tomorrow"]
    ) -> str:
        user_data = await self.bot_service.get_user(chat_id)
        if forecast_time == "today":
            return await get_merged_forecasts(
                chat_id, user_data, self.bot_service.get_today_weather_forecast
            )
        elif forecast_time == "tomorrow":
            return await get_merged_forecasts(
                chat_id, user_data, self.bot_service.get_tomorrow_weather_forecast
            )
        else:
            assert_never(forecast_time)

    def _route_extra_help(self, help_value: str | None) -> str:
        assert help_value is not None, "bot_router guarantee this won't be None"
        match help_value:
            # add more extra help
            case "location":
                return message_container.SHOW_LOCATION_COMMAND_HELP
            case "input":
                return message_container.SHOW_INPUT_COMMAND_HELP
            case "today":
                return message_container.SHOW_TODAY_COMMAND_HELP
            case "tomorrow":
                return message_container.SHOW_TOMORROW_COMMAND_HELP
            case _:
                return message_container.show_invalid_extra_help_value_message(
                    help_value
                )

    async def _reset_location(self, chat_id: int) -> str:
        await self._reset_user_state_data(chat_id)
        return message_container.TELLS_USER_RESET_SUCCESS

    async def _persist_location_result(
        self, chat_id: int, flow_result: LocationFlowResult | LocationFlowResultComplete
    ) -> None:
        if flow_result.bot_user_state is not None:
            await self.bot_service.create_or_update_user_state(
                flow_result.bot_user_state
            )
        if isinstance(flow_result, LocationFlowResultComplete):
            await self.bot_service.create_or_update_user(
                BotUserModel(chat_id=chat_id, adm4_code=flow_result.adm4_code)
            )

    async def _handle_when_user_data_is_missing(
        self,
        chat_id: int,
    ) -> UserDataRestorationResult:
        """
        In case user or user.kode_adm4 missing from db, try to restore it
        using the user state data.
        """
        logger.debug(f"start restore attempt for missing user {chat_id} data")
        user_state = await self.bot_service.get_user_state(chat_id)
        if user_state is None:
            logger.debug(f"restore attempt for missing user {chat_id} data failed")
            return UserDataRestorationResult.FAILED
        try:
            adm4_code = await self.location_flow_handler.get_adm4_code_or_raise(
                chat_id, user_state
            )
            await self.bot_service.create_or_update_user(
                BotUserModel(chat_id, adm4_code=adm4_code)
            )
            logger.debug(f"restore attempt for missing user {chat_id} data success")
            return UserDataRestorationResult.SUCCESS
        except DataIntegrityError:
            logger.debug(f"restore attempt for missing user {chat_id} data failed")
            return UserDataRestorationResult.FAILED

    async def _reset_user_state_data(
        self, chat_id: int, with_user_data: bool = False
    ) -> None:
        """
        Reset the state of a user, with optional 'with_user_data' bool,
        to also reset the user data on the database.
        """
        if with_user_data:
            await asyncio.gather(
                self.bot_service.create_or_update_user(BotUserModel(chat_id)),
                self.bot_service.create_or_update_user_state(
                    BotUserStateModel(chat_id)
                ),
            )
            logger.debug(f"user {chat_id} state and data reset")
            return
        await self.bot_service.create_or_update_user_state(BotUserStateModel(chat_id))
        logger.debug(f"user {chat_id} state reset")
