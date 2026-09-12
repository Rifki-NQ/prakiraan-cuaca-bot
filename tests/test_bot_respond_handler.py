# pyright: reportPrivateUsage=false
import pytest
from unittest.mock import patch, AsyncMock
from tests.mock_class.mock_bot_service import MockBotService
from tests.mock_class.mock_location_flow_handler import (
    MockLocationFlowHandlerNoError,
    MockLocationFlowHandlerWithError,
)
from src.bot.bot_respond_handler import BotRespondHandler
from src.bot.location_flow_handler import LocationFlowHandler
from src.bot import message_container
from src.models.domain_model import (
    BotUserStateModel,
    LocationFlowResult,
    LocationFlowResultComplete,
)
from src.models.contexts import BotUserStateContext
from src.models.enums import (
    BotAction,
    Commands,
    UserLocationState,
    UserDataRestorationResult,
)
from src.exceptions import DataIntegrityError


FAKE_CHAT_ID = 1
FAKE_INPUT_VALUE = "fake input"
FAKE_LIST_VALUE = "fake list value"
FAKE_BOT_USER_STATE = BotUserStateModel(chat_id=FAKE_CHAT_ID)
FAKE_USER_LOCATION_STATE = UserLocationState.NO_STATE
FAKE_BOT_USER_STATE_CONTEXT = BotUserStateContext(
    user_location_state=FAKE_USER_LOCATION_STATE, bot_user_state=FAKE_BOT_USER_STATE
)


@pytest.fixture
def bot_respond_handler() -> BotRespondHandler:
    """
    Fixture of BotRespondHandler where no error is raised
    from both mock class.
    """
    return BotRespondHandler(MockBotService(), MockLocationFlowHandlerNoError())


@pytest.fixture
def bot_respond_handler_err() -> BotRespondHandler:
    """
    Fixture of BotRespondHandler where DataIntegrityError
    is always raised from all methods of
    the mocked LocationFlowHandler class.
    """
    return BotRespondHandler(MockBotService(), MockLocationFlowHandlerWithError())


class TestParseCommand:
    """A group of test cases for BotRespondHandler.parse_command()"""

    COMMAND_EXAMPLE = Commands.START  # can be anything as long as its Commands' member

    # special case for BotAction.ASK_SUBDISTRICT and BotAction.ASK_VILLAGE,
    # because it calls external method inside the message_container function,
    # its tested in test_for_branches_that_calls_location_flow_handler_method
    @pytest.mark.parametrize(
        "bot_action, expected_output",
        [
            ((BotAction.SHOW_INTRO,), message_container.SHOW_INTRO),
            ((BotAction.SHOW_HELP,), message_container.SHOW_HELP),
            ((BotAction.ASK_CITY_OR_REGENCY,), message_container.ASK_CITY_OR_REGENCY),
            (
                (BotAction.TELLS_USER_LOCATION_SETUP_FINISHED,),
                message_container.TELLS_USER_LOCATION_SETUP_FINISHED,
            ),
            (
                (BotAction.TELLS_USER_TO_ADD_INPUT_VALUE,),
                message_container.notify_to_add_input_value(COMMAND_EXAMPLE.value),
            ),
            (
                (BotAction.TELLS_USER_TO_SET_LOCATION,),
                message_container.TELLS_USER_TO_SET_LOCATION,
            ),
            (
                (BotAction.TELLS_USER_TO_FINISH_SET_LOCATION,),
                message_container.TELLS_USER_TO_FINISH_SET_LOCATION,
            ),
            (
                (BotAction.SHOW_WELCOME_BACK_INTRO,),
                message_container.SHOW_WELCOME_BACK_INTRO,
            ),
            (
                (BotAction.TELLS_USER_NO_NEED_FOR_RESET,),
                message_container.TELLS_USER_NO_NEED_FOR_RESET,
            ),
            (
                (BotAction.TELLS_USER_NO_NEED_FOR_REVERT,),
                message_container.TELLS_USER_NO_NEED_FOR_REVERT,
            ),
            (
                (BotAction.TELLS_USER_NO_NEED_FOR_INPUT_VALUE,),
                message_container.notify_to_not_add_input_value(COMMAND_EXAMPLE.value),
            ),
        ],
    )
    async def test_for_branches_that_return_message_container_string(
        self,
        bot_respond_handler: BotRespondHandler,
        bot_action: tuple[BotAction, ...],
        expected_output: str,
    ) -> None:
        """Test that parse_command() return the right string from message_container"""
        with (
            patch("src.bot.bot_respond_handler.route_command", return_value=bot_action),
            patch.object(
                bot_respond_handler.bot_service,
                "resolve_user_location_state",
                new_callable=AsyncMock,
                return_value=FAKE_BOT_USER_STATE_CONTEXT,
            ),
        ):
            result = await bot_respond_handler.parse_command(
                chat_id=FAKE_CHAT_ID,
                command=self.COMMAND_EXAMPLE,
                input_value=FAKE_INPUT_VALUE,
            )
        assert result == expected_output

    @pytest.mark.parametrize(
        "bot_action, should_call",
        [
            (
                BotAction.SHOW_EXTRA_HELP,
                BotRespondHandler._route_extra_help.__name__,
            ),
            (
                BotAction.RECEIVE_INPUT_FOR_CITY_OR_REGENCY,
                BotRespondHandler._handle_input_for_city_or_regency.__name__,
            ),
            (
                BotAction.RECEIVE_INPUT_FOR_SUBDISTRICT,
                BotRespondHandler._handle_input_for_subdistrict_and_village.__name__,
            ),
            (
                BotAction.RECEIVE_INPUT_FOR_VILLAGE,
                BotRespondHandler._handle_input_for_subdistrict_and_village.__name__,
            ),
            (
                BotAction.SHOW_USER_CURRENT_LOCATION,
                BotRespondHandler._handle_show_user_current_location.__name__,
            ),
            (
                BotAction.SHOW_TODAY_FORECASTS,
                BotRespondHandler._get_forecast_message.__name__,
            ),
            (
                BotAction.SHOW_TOMORROW_FORECASTS,
                BotRespondHandler._get_forecast_message.__name__,
            ),
            (BotAction.RESET_USER_LOCATION, BotRespondHandler._reset_location.__name__),
            (
                BotAction.REVERT_USER_LOCATION_STATE,
                BotRespondHandler._revert_location_state.__name__,
            ),
        ],
    )
    async def test_for_branches_that_calls_internal_method(
        self,
        bot_respond_handler: BotRespondHandler,
        bot_action: BotAction,
        should_call: str,
    ) -> None:
        """Test that parse_command() calls the right internal method with the right args"""
        with (
            patch(
                "src.bot.bot_respond_handler.route_command", return_value=(bot_action,)
            ),
            patch.object(
                bot_respond_handler, should_call, return_value="fake respond message"
            ) as mock_method,
            patch.object(
                bot_respond_handler.bot_service,
                "resolve_user_location_state",
                new_callable=AsyncMock,
                return_value=FAKE_BOT_USER_STATE_CONTEXT,
            ),
        ):
            result = await bot_respond_handler.parse_command(
                chat_id=FAKE_CHAT_ID,
                command=self.COMMAND_EXAMPLE,
                input_value=FAKE_INPUT_VALUE,
            )
        assert result == "fake respond message"
        match bot_action:
            case BotAction.SHOW_EXTRA_HELP:
                mock_method.assert_called_once_with(FAKE_INPUT_VALUE)
            case BotAction.RECEIVE_INPUT_FOR_CITY_OR_REGENCY:
                mock_method.assert_awaited_once_with(FAKE_CHAT_ID, FAKE_INPUT_VALUE)
            case BotAction.RECEIVE_INPUT_FOR_SUBDISTRICT:
                mock_method.assert_awaited_once_with(
                    FAKE_CHAT_ID,
                    FAKE_BOT_USER_STATE_CONTEXT.bot_user_state,
                    FAKE_INPUT_VALUE,
                    bot_respond_handler.location_flow_handler.handle_input_for_subdistrict,
                )
            case BotAction.RECEIVE_INPUT_FOR_VILLAGE:
                mock_method.assert_awaited_once_with(
                    FAKE_CHAT_ID,
                    FAKE_BOT_USER_STATE_CONTEXT.bot_user_state,
                    FAKE_INPUT_VALUE,
                    bot_respond_handler.location_flow_handler.handle_input_for_village,
                )
            case BotAction.SHOW_USER_CURRENT_LOCATION:
                mock_method.assert_awaited_once_with(FAKE_CHAT_ID)
            case BotAction.SHOW_TODAY_FORECASTS:
                mock_method.assert_awaited_once_with(FAKE_CHAT_ID, "today")
            case BotAction.SHOW_TOMORROW_FORECASTS:
                mock_method.assert_awaited_once_with(FAKE_CHAT_ID, "tomorrow")
            case BotAction.RESET_USER_LOCATION:
                mock_method.assert_awaited_once_with(FAKE_CHAT_ID)
            case BotAction.REVERT_USER_LOCATION_STATE:
                mock_method.assert_awaited_once_with(
                    FAKE_CHAT_ID, FAKE_BOT_USER_STATE_CONTEXT.bot_user_state
                )
            case _:
                assert False, f"test branch missing: {bot_action}"

    @pytest.mark.parametrize(
        "bot_action, should_call",
        [
            (
                BotAction.ASK_SUBDISTRICT,
                LocationFlowHandler.get_merged_subdistrict_list.__name__,
            ),
            (
                BotAction.ASK_VILLAGE,
                LocationFlowHandler.get_merged_village_list.__name__,
            ),
        ],
    )
    async def test_for_branches_that_calls_location_flow_handler_method(
        self,
        bot_respond_handler: BotRespondHandler,
        bot_action: BotAction,
        should_call: str,
    ) -> None:
        """
        Test that parse_command() calls the right LocationFlowHandler's method
        with the right args
        """
        with (
            patch(
                "src.bot.bot_respond_handler.route_command", return_value=(bot_action,)
            ),
            patch.object(
                bot_respond_handler.location_flow_handler,
                should_call,
                return_value=FAKE_LIST_VALUE,
            ) as mock_method,
            patch.object(
                bot_respond_handler.bot_service,
                "resolve_user_location_state",
                new_callable=AsyncMock,
                return_value=FAKE_BOT_USER_STATE_CONTEXT,
            ),
        ):
            result = await bot_respond_handler.parse_command(
                chat_id=FAKE_CHAT_ID,
                command=self.COMMAND_EXAMPLE,
                input_value=FAKE_INPUT_VALUE,
            )
        match bot_action:
            case BotAction.ASK_SUBDISTRICT:
                assert result == message_container.notify_to_choose_subdistrict(
                    FAKE_LIST_VALUE
                )
                mock_method.assert_awaited_once_with(
                    FAKE_CHAT_ID, FAKE_BOT_USER_STATE_CONTEXT.bot_user_state
                )
            case BotAction.ASK_VILLAGE:
                assert result == message_container.notify_to_choose_village(
                    FAKE_LIST_VALUE
                )
                mock_method.assert_awaited_once_with(
                    FAKE_CHAT_ID, FAKE_BOT_USER_STATE_CONTEXT.bot_user_state
                )
            case _:
                assert False, f"test branch missing: {bot_action}"

    async def test_bot_respond_message_is_merged(
        self, bot_respond_handler: BotRespondHandler
    ) -> None:
        """
        Test that parse_command() merge the respond messages,
        when the BotAction is more than one value in the tuple from route_command().
        """
        with (
            patch(
                "src.bot.bot_respond_handler.route_command",
                return_value=(BotAction.SHOW_INTRO, BotAction.SHOW_HELP),
            ),
            patch.object(
                bot_respond_handler.bot_service,
                "resolve_user_location_state",
                new_callable=AsyncMock,
                return_value=FAKE_BOT_USER_STATE_CONTEXT,
            ),
        ):
            result = await bot_respond_handler.parse_command(
                chat_id=FAKE_CHAT_ID,
                command=self.COMMAND_EXAMPLE,
                input_value=FAKE_INPUT_VALUE,
            )
        assert (
            result == f"{message_container.SHOW_INTRO}\n\n{message_container.SHOW_HELP}"
        )


async def test_handle_input_for_city_or_regency_without_data_error(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    result = await bot_respond_handler._handle_input_for_city_or_regency(
        chat_id=FAKE_CHAT_ID, input_value=FAKE_INPUT_VALUE
    )
    assert "create_or_update_user_state called" in caplog.messages[0]
    assert result == "fake flow result"


async def test_handle_input_for_city_or_regency_with_data_error(
    bot_respond_handler_err: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    with pytest.raises(DataIntegrityError) as exc_info:
        await bot_respond_handler_err._handle_input_for_city_or_regency(
            chat_id=FAKE_CHAT_ID, input_value=FAKE_INPUT_VALUE
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert exc_info.value.message == "fake error"
    assert "create_or_update_user_state called" in caplog.messages
    assert f"user {FAKE_CHAT_ID} state reset" in caplog.messages


async def test_handle_input_for_subdistrict_and_village_for_subdistrict_without_data_error(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    result = await bot_respond_handler._handle_input_for_subdistrict_and_village(
        chat_id=FAKE_CHAT_ID,
        user_state=FAKE_BOT_USER_STATE,
        input_value=FAKE_INPUT_VALUE,
        flow_handler=bot_respond_handler.location_flow_handler.handle_input_for_subdistrict,
    )
    assert "create_or_update_user_state called" in caplog.messages[0]
    assert result == "fake flow result"


async def test_handle_input_for_subdistrict_and_village_for_subdistrict_with_data_error(
    bot_respond_handler_err: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    with pytest.raises(DataIntegrityError) as exc_info:
        await bot_respond_handler_err._handle_input_for_subdistrict_and_village(
            chat_id=FAKE_CHAT_ID,
            user_state=FAKE_BOT_USER_STATE,
            input_value=FAKE_INPUT_VALUE,
            flow_handler=bot_respond_handler_err.location_flow_handler.handle_input_for_subdistrict,
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert exc_info.value.message == "fake error"
    assert "create_or_update_user_state called" in caplog.messages
    assert f"user {FAKE_CHAT_ID} state reset" in caplog.messages


async def test_handle_input_for_subdistrict_and_village_for_village_without_data_error(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    result = await bot_respond_handler._handle_input_for_subdistrict_and_village(
        chat_id=FAKE_CHAT_ID,
        user_state=FAKE_BOT_USER_STATE,
        input_value=FAKE_INPUT_VALUE,
        flow_handler=bot_respond_handler.location_flow_handler.handle_input_for_village,
    )
    assert "create_or_update_user_state called" in caplog.messages
    assert "create_or_update_user called" in caplog.messages
    assert result == "fake complete flow result"


async def test_handle_input_for_subdistrict_and_village_for_village_with_data_error(
    bot_respond_handler_err: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    with pytest.raises(DataIntegrityError) as exc_info:
        await bot_respond_handler_err._handle_input_for_subdistrict_and_village(
            chat_id=FAKE_CHAT_ID,
            user_state=FAKE_BOT_USER_STATE,
            input_value=FAKE_INPUT_VALUE,
            flow_handler=bot_respond_handler_err.location_flow_handler.handle_input_for_village,
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert exc_info.value.message == "fake error"
    assert "create_or_update_user_state called" in caplog.messages
    assert f"user {FAKE_CHAT_ID} state reset" in caplog.messages


class TestHandleShowUserCurrentLocation:
    """A group of test cases for BotRespondHandler._handle_show_user_current_location()"""

    async def test_without_data_error(
        self, bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        result = await bot_respond_handler._handle_show_user_current_location(
            chat_id=FAKE_CHAT_ID
        )
        assert result == "fake address"
        assert "get_user called" in caplog.messages

    async def test_with_data_error_where_data_restoration_success(
        self,
        bot_respond_handler_err: BotRespondHandler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(10)
        with (
            patch.object(
                bot_respond_handler_err,
                "_handle_when_user_data_is_missing",
                new_callable=AsyncMock,
                return_value=UserDataRestorationResult.SUCCESS,
            ),
            patch.object(
                bot_respond_handler_err.location_flow_handler,
                "get_full_address",
                new_callable=AsyncMock,
                side_effect=[
                    DataIntegrityError(chat_id=1, message="fake error"),
                    "fake address",
                ],
            ),
        ):
            result = await bot_respond_handler_err._handle_show_user_current_location(
                chat_id=FAKE_CHAT_ID
            )
        assert result == "fake address"
        assert "get_user called" in caplog.messages

    async def test_with_data_error_where_data_restoration_success_then_data_error_again(
        self,
        bot_respond_handler_err: BotRespondHandler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(10)
        with (
            patch.object(
                bot_respond_handler_err,
                "_handle_when_user_data_is_missing",
                new_callable=AsyncMock,
                return_value=UserDataRestorationResult.SUCCESS,
            ),
            pytest.raises(DataIntegrityError) as exc_info,
        ):
            await bot_respond_handler_err._handle_show_user_current_location(
                chat_id=FAKE_CHAT_ID
            )
        assert exc_info.value.chat_id == FAKE_CHAT_ID
        assert exc_info.value.message == "fake error"
        assert "create_or_update_user called" in caplog.messages
        assert "create_or_update_user_state called" in caplog.messages
        assert f"user {FAKE_CHAT_ID} state and data reset" in caplog.messages

    async def test_with_data_error_where_data_restoration_failed(
        self,
        bot_respond_handler_err: BotRespondHandler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(10)
        with pytest.raises(DataIntegrityError) as exc_info:
            with patch.object(
                bot_respond_handler_err,
                "_handle_when_user_data_is_missing",
                new_callable=AsyncMock,
                return_value=UserDataRestorationResult.FAILED,
            ):
                await bot_respond_handler_err._handle_show_user_current_location(
                    chat_id=FAKE_CHAT_ID
                )
        assert exc_info.value.chat_id == FAKE_CHAT_ID
        assert exc_info.value.message == "fake error"
        assert "create_or_update_user called" in caplog.messages
        assert "create_or_update_user_state called" in caplog.messages
        assert f"user {FAKE_CHAT_ID} state and data reset" in caplog.messages


async def test_get_user_then_get_full_address_without_data_error(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    result = await bot_respond_handler._get_user_then_get_full_address(
        chat_id=FAKE_CHAT_ID
    )
    assert result == "fake address"
    assert "get_user called" in caplog.messages


async def test_get_user_then_get_full_address_with_data_error(
    bot_respond_handler_err: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    with pytest.raises(DataIntegrityError) as exc_info:
        await bot_respond_handler_err._get_user_then_get_full_address(
            chat_id=FAKE_CHAT_ID
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert exc_info.value.message == "fake error"


async def test_get_forecast_message_with_today_forecast_datetime(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    with patch(
        "src.bot.bot_respond_handler.get_merged_forecasts",
        new_callable=AsyncMock,
        return_value="fake merged forecasts",
    ) as mock_get_merged:
        result = await bot_respond_handler._get_forecast_message(
            chat_id=FAKE_CHAT_ID, forecast_time="today"
        )
    assert result == "fake merged forecasts"
    assert "get_user called" in caplog.messages
    mock_get_merged.assert_called_once_with(
        FAKE_CHAT_ID, None, bot_respond_handler.bot_service.get_today_weather_forecast
    )


async def test_get_forecast_message_with_tomorrow_forecast_datetime(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    with patch(
        "src.bot.bot_respond_handler.get_merged_forecasts",
        new_callable=AsyncMock,
        return_value="fake merged forecasts",
    ) as mock_get_merged:
        result = await bot_respond_handler._get_forecast_message(
            chat_id=FAKE_CHAT_ID, forecast_time="tomorrow"
        )
    assert result == "fake merged forecasts"
    assert "get_user called" in caplog.messages
    mock_get_merged.assert_called_once_with(
        FAKE_CHAT_ID,
        None,
        bot_respond_handler.bot_service.get_tomorrow_weather_forecast,
    )


async def test_get_forecast_message_with_invalid_forecast_datetime_arg(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    with pytest.raises(AssertionError):
        await bot_respond_handler._get_forecast_message(
            chat_id=FAKE_CHAT_ID,
            forecast_time="besok",  # type: ignore
        )
    assert "get_user called" in caplog.messages


@pytest.mark.parametrize(
    "help_value, expected_output",
    [
        ("location", message_container.SHOW_LOCATION_COMMAND_HELP),
        ("input", message_container.SHOW_INPUT_COMMAND_HELP),
        ("today", message_container.SHOW_TODAY_COMMAND_HELP),
        ("tomorrow", message_container.SHOW_TOMORROW_COMMAND_HELP),
        ("reset", message_container.SHOW_RESET_COMMAND_HELP),
        ("revert", message_container.SHOW_REVERT_COMMAND_HELP),
        (
            "invalid_help_value",
            message_container.show_invalid_extra_help_value_message(
                "invalid_help_value"
            ),
        ),
    ],
)
def test_route_extra_help(
    bot_respond_handler: BotRespondHandler, help_value: str, expected_output: str
) -> None:
    result = bot_respond_handler._route_extra_help(help_value)
    assert result == expected_output


async def test_reset_location(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    result = await bot_respond_handler._reset_location(chat_id=FAKE_CHAT_ID)
    assert result == message_container.TELLS_USER_RESET_SUCCESS
    assert "create_or_update_user_state called" in caplog.messages
    assert f"user {FAKE_CHAT_ID} state reset" in caplog.messages


async def test_revert_location_state(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    result = await bot_respond_handler._revert_location_state(
        chat_id=FAKE_CHAT_ID, user_state=FAKE_BOT_USER_STATE
    )
    assert result == "fake flow result"
    assert "create_or_update_user_state called" in caplog.messages


class TestPersistLocationFlowResult:
    """A group of test cases for BotRespondHandler._persist_location_flow_result()"""

    async def test_location_flow_result_obj_with_not_none_user_state(
        self, bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        await bot_respond_handler._persist_location_flow_result(
            chat_id=FAKE_CHAT_ID,
            flow_result=LocationFlowResult(
                bot_user_state=FAKE_BOT_USER_STATE, message="fake flow result"
            ),
        )
        assert "create_or_update_user_state called" in caplog.messages

    async def test_location_flow_result_obj_with_none_user_state(
        self, bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        await bot_respond_handler._persist_location_flow_result(
            chat_id=FAKE_CHAT_ID,
            flow_result=LocationFlowResult(
                bot_user_state=None, message="fake flow result"
            ),
        )
        assert "create_or_update_user_state called" not in caplog.messages

    async def test_location_flow_result_complete_obj(
        self, bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        await bot_respond_handler._persist_location_flow_result(
            chat_id=FAKE_CHAT_ID,
            flow_result=LocationFlowResultComplete(
                bot_user_state=FAKE_BOT_USER_STATE,
                message="fake complete flow result",
                adm4_code="fake_adm4_code",
            ),
        )
        assert "create_or_update_user called" in caplog.messages


class TestHandleWhenUserDataIsMissing:
    """A group of test cases for BotRespondHandler._handle_when_user_data_is_missing()"""

    async def test_when_data_restoration_is_successfull(
        self, bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        with patch.object(
            bot_respond_handler.bot_service,
            "get_user_state",
            new_callable=AsyncMock,
            return_value=FAKE_BOT_USER_STATE,
        ):
            result = await bot_respond_handler._handle_when_user_data_is_missing(
                chat_id=FAKE_CHAT_ID
            )
        assert result == UserDataRestorationResult.SUCCESS
        assert "create_or_update_user called" in caplog.messages
        assert f"restore attempt for missing user {FAKE_CHAT_ID} data success"

    async def test_when_get_user_state_return_none(
        self, bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(10)
        with patch.object(
            bot_respond_handler.bot_service,
            "get_user_state",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await bot_respond_handler._handle_when_user_data_is_missing(
                chat_id=FAKE_CHAT_ID
            )
        assert result == UserDataRestorationResult.FAILED
        assert (
            f"restore attempt for missing user {FAKE_CHAT_ID} data failed"
            in caplog.messages
        )

    async def test_when_get_adm4_code_raise_data_error(
        self,
        bot_respond_handler_err: BotRespondHandler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(10)
        result = await bot_respond_handler_err._handle_when_user_data_is_missing(
            chat_id=FAKE_CHAT_ID
        )
        assert result == UserDataRestorationResult.FAILED
        assert (
            f"restore attempt for missing user {FAKE_CHAT_ID} data failed"
            in caplog.messages
        )


async def test_reset_user_state_data_without_user_data(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    await bot_respond_handler._reset_user_state_data(
        chat_id=FAKE_CHAT_ID, with_user_data=False
    )
    assert "create_or_update_user_state called" in caplog.messages
    assert f"user {FAKE_CHAT_ID} state reset" in caplog.messages


async def test_reset_user_state_data_with_user_data(
    bot_respond_handler: BotRespondHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(10)
    await bot_respond_handler._reset_user_state_data(
        chat_id=FAKE_CHAT_ID, with_user_data=True
    )
    assert "create_or_update_user called" in caplog.messages
    assert "create_or_update_user_state called" in caplog.messages
    assert f"user {FAKE_CHAT_ID} state and data reset" in caplog.messages
