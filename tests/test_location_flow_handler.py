import pytest
import pytest_asyncio
from dotenv import load_dotenv
from src.main import get_env
from src.queries.sqlite_query import LocationFinder
from src.bot.location_flow_handler import LocationFlowHandler
from src.models.domain_model import (
    BotUserModel,
    BotUserStateModel,
    LocationFlowResult,
    LocationFlowResultComplete,
)
from src.models.enums import UserStateCheckLevel
from src.exceptions import DataIntegrityError


load_dotenv()
local_db_url = get_env("TEST_LOCAL_DATABASE_URL")
FAKE_CHAT_ID = 123


@pytest_asyncio.fixture
async def location_flow_handler() -> LocationFlowHandler:
    location_finder = LocationFinder()
    await location_finder.setup_local_db(local_db_url)
    return LocationFlowHandler(location_finder)


@pytest.fixture
def only_chat_id_user_state() -> BotUserStateModel:
    return BotUserStateModel(chat_id=FAKE_CHAT_ID)


@pytest.fixture
def state_at_kabupaten_atau_kota_user_state() -> BotUserStateModel:
    return BotUserStateModel(
        chat_id=FAKE_CHAT_ID,
        kabupaten_atau_kota="kabupaten bekasi",
    )


@pytest.fixture
def state_at_kecamatan_user_state() -> BotUserStateModel:
    return BotUserStateModel(
        chat_id=FAKE_CHAT_ID,
        kabupaten_atau_kota="kabupaten bekasi",
        kecamatan="cikarang pusat",
    )


@pytest.fixture
def completed_user_state() -> BotUserStateModel:
    return BotUserStateModel(
        chat_id=FAKE_CHAT_ID,
        kabupaten_atau_kota="kabupaten bekasi",
        kecamatan="cikarang pusat",
        desa_atau_kelurahan="sukamahi",
    )


def _only_chat_id_user_state() -> BotUserStateModel:
    return BotUserStateModel(chat_id=FAKE_CHAT_ID)


def _state_at_kabupaten_atau_kota_user_state() -> BotUserStateModel:
    return BotUserStateModel(
        chat_id=FAKE_CHAT_ID,
        kabupaten_atau_kota="kabupaten bekasi",
    )


def _state_at_kecamatan_user_state() -> BotUserStateModel:
    return BotUserStateModel(
        chat_id=FAKE_CHAT_ID,
        kabupaten_atau_kota="kabupaten bekasi",
        kecamatan="cikarang pusat",
    )


def _completed_user_state() -> BotUserStateModel:
    return BotUserStateModel(
        chat_id=FAKE_CHAT_ID,
        kabupaten_atau_kota="kabupaten bekasi",
        kecamatan="cikarang pusat",
        desa_atau_kelurahan="sukamahi",
    )


async def test_handle_input_for_city_or_regency_location_found(
    location_flow_handler: LocationFlowHandler,
) -> None:
    input = "kabupaten bekasi"
    result = await location_flow_handler.handle_input_for_city_or_regency(
        chat_id=FAKE_CHAT_ID, city_or_regency=input
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is not None
    assert result.bot_user_state.chat_id == FAKE_CHAT_ID
    assert result.bot_user_state.kabupaten_atau_kota == input
    assert result.bot_user_state.kecamatan is None
    assert result.bot_user_state.desa_atau_kelurahan is None

    assert f"updated to <b>{input}</b>" in result.message
    assert "Select your <b>subdistrict</b>" in result.message


async def test_handle_input_for_city_or_regency_location_no_exact_match(
    location_flow_handler: LocationFlowHandler,
) -> None:
    """
    In case user send an input where there are multiple location
    for the given input, for example 'bekasi' can mean
    either kabupaten bekasi or kota bekasi.
    """
    input = "bekasi"
    result = await location_flow_handler.handle_input_for_city_or_regency(
        chat_id=FAKE_CHAT_ID, city_or_regency=input
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is None
    assert "Select your <b>city or regency</b> from the list" in result.message


async def test_handle_input_for_city_or_regency_location_not_found(
    location_flow_handler: LocationFlowHandler,
) -> None:
    """
    In case user send an input where there is no location found
    for that input.
    """
    input = "isakeb"
    result = await location_flow_handler.handle_input_for_city_or_regency(
        chat_id=FAKE_CHAT_ID, city_or_regency=input
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is None
    assert "<b>isakeb</b> not found" in result.message


async def test_handle_input_for_subdistrict_location_found(
    state_at_kabupaten_atau_kota_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    input = "cikarang selatan"
    user_state = state_at_kabupaten_atau_kota_user_state
    result = await location_flow_handler.handle_input_for_subdistrict(
        chat_id=FAKE_CHAT_ID, user_state=user_state, subdistrict=input
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is not None
    assert result.bot_user_state.chat_id == FAKE_CHAT_ID
    assert result.bot_user_state.kabupaten_atau_kota == user_state.kabupaten_atau_kota
    assert result.bot_user_state.kecamatan == input
    assert result.bot_user_state.desa_atau_kelurahan is None

    assert f"updated to <b>{input}</b>" in result.message
    assert "Select your <b>village</b>" in result.message


async def test_handle_input_for_subdistrict_location_not_found(
    state_at_kabupaten_atau_kota_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    input = "cikarang sebelah kanan"
    user_state = state_at_kabupaten_atau_kota_user_state
    result = await location_flow_handler.handle_input_for_subdistrict(
        chat_id=FAKE_CHAT_ID, user_state=user_state, subdistrict=input
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is None
    assert "select from the list" in result.message


async def test_handle_input_for_village_location_found(
    state_at_kecamatan_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    input = "sukamahi"
    user_state = state_at_kecamatan_user_state
    result = await location_flow_handler.handle_input_for_village(
        chat_id=FAKE_CHAT_ID, user_state=user_state, village=input
    )
    assert isinstance(result, LocationFlowResultComplete)
    assert result.bot_user_state.chat_id == FAKE_CHAT_ID
    assert result.bot_user_state.kabupaten_atau_kota == user_state.kabupaten_atau_kota
    assert result.bot_user_state.kecamatan == user_state.kecamatan
    assert result.bot_user_state.desa_atau_kelurahan == input
    assert result.adm4_code == "32.16.20.2002"

    assert f"updated to <b>{input}</b>" in result.message
    assert "address updated" in result.message


async def test_handle_input_for_village_location_not_found(
    state_at_kecamatan_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    input = "okkkk"
    user_state = state_at_kecamatan_user_state
    result = await location_flow_handler.handle_input_for_village(
        chat_id=FAKE_CHAT_ID, user_state=user_state, village=input
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is None
    assert "select from the list" in result.message


async def test_revert_location_state_kabupaten_atau_kota_is_none(
    only_chat_id_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    user_state = only_chat_id_user_state
    result = await location_flow_handler.revert_location_state(
        chat_id=FAKE_CHAT_ID, user_state=user_state
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is not None
    assert result.bot_user_state.chat_id == FAKE_CHAT_ID
    assert result.bot_user_state.kabupaten_atau_kota is None
    assert result.bot_user_state.kecamatan is None
    assert result.bot_user_state.desa_atau_kelurahan is None

    assert "Enter your <b>city or regency</b>" in result.message


async def test_revert_location_state_kecamatan_is_none(
    state_at_kabupaten_atau_kota_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    user_state = state_at_kabupaten_atau_kota_user_state
    result = await location_flow_handler.revert_location_state(
        chat_id=FAKE_CHAT_ID, user_state=user_state
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is not None
    assert result.bot_user_state.chat_id == FAKE_CHAT_ID
    assert result.bot_user_state.kabupaten_atau_kota is None
    assert result.bot_user_state.kecamatan is None
    assert result.bot_user_state.desa_atau_kelurahan is None

    assert "<b>city or regency</b> reverted" in result.message
    assert "Enter your <b>city or regency</b>" in result.message


async def test_revert_location_state_desa_atau_kelurahan_is_none(
    state_at_kecamatan_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    user_state = state_at_kecamatan_user_state
    result = await location_flow_handler.revert_location_state(
        chat_id=FAKE_CHAT_ID, user_state=user_state
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is not None
    assert result.bot_user_state.chat_id == FAKE_CHAT_ID
    assert result.bot_user_state.kabupaten_atau_kota == user_state.kabupaten_atau_kota
    assert result.bot_user_state.kecamatan is None
    assert result.bot_user_state.desa_atau_kelurahan is None

    assert "<b>subdistrict</b> reverted" in result.message
    assert "Select your <b>subdistrict</b>" in result.message


async def test_revert_location_state_on_completed_user_state(
    completed_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    user_state = completed_user_state
    result = await location_flow_handler.revert_location_state(
        chat_id=FAKE_CHAT_ID, user_state=user_state
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state is not None
    assert result.bot_user_state.chat_id == FAKE_CHAT_ID
    assert result.bot_user_state.kabupaten_atau_kota == user_state.kabupaten_atau_kota
    assert result.bot_user_state.kecamatan == user_state.kecamatan
    assert result.bot_user_state.desa_atau_kelurahan is None

    assert "<b>village</b> reverted" in result.message
    assert "Select your <b>village</b>" in result.message


async def test_get_full_address_found(
    location_flow_handler: LocationFlowHandler,
) -> None:
    user_data = BotUserModel(chat_id=FAKE_CHAT_ID, adm4_code="32.16.20.2002")
    result = await location_flow_handler.get_full_address(
        chat_id=FAKE_CHAT_ID, user_data=user_data
    )
    assert "kabupaten bekasi" in result
    assert "cikarang pusat" in result
    assert "sukamahi" in result
    assert "32.16.20.2002" in result


async def test_get_full_address_not_found(
    location_flow_handler: LocationFlowHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(40)  # level: ERROR
    user_data = BotUserModel(chat_id=FAKE_CHAT_ID, adm4_code="fake_adm4_code")
    with pytest.raises(DataIntegrityError) as exc_info:
        await location_flow_handler.get_full_address(
            chat_id=FAKE_CHAT_ID, user_data=user_data
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert "re-input your entire" in exc_info.value.message
    assert "no address found for the adm4_code: fake_adm4_code" in caplog.messages[0]


async def test_get_adm4_code_or_raise_found(
    completed_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(40)  # level: ERROR
    user_state = completed_user_state
    result = await location_flow_handler.get_adm4_code_or_raise(
        chat_id=FAKE_CHAT_ID, user_state=user_state
    )
    assert result == "32.16.20.2002"


async def test_get_adm4_code_or_raise_not_found(
    location_flow_handler: LocationFlowHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(40)  # level: ERROR
    user_state = BotUserStateModel(
        chat_id=FAKE_CHAT_ID,
        kabupaten_atau_kota="kabupaten bekasi",
        kecamatan="cikarang pusat",
        desa_atau_kelurahan="wkwkwk",  # <- invalid / non-existent village
    )
    with pytest.raises(DataIntegrityError) as exc_info:
        await location_flow_handler.get_adm4_code_or_raise(
            chat_id=FAKE_CHAT_ID, user_state=user_state
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert "re-input your entire" in exc_info.value.message
    assert (
        f"validated city_or_regency: {user_state.kabupaten_atau_kota}"
        in caplog.messages[0]
    )
    assert f"validated subdistrict: {user_state.kecamatan}" in caplog.messages[0]
    assert f"validated village: {user_state.desa_atau_kelurahan}" in caplog.messages[0]


# this test only the happy path, since the failure path
# is owned by the helper methods
async def test_get_merged_subdistrict_list(
    state_at_kabupaten_atau_kota_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    user_state = state_at_kabupaten_atau_kota_user_state
    result = await location_flow_handler.get_merged_subdistrict_list(
        chat_id=FAKE_CHAT_ID, user_state=user_state
    )
    assert "- cikarang pusat" in result
    assert "- cikarang selatan" in result
    assert "- serang baru" in result
    assert "- setu" in result


# this test only the happy path, since the failure path
# is owned by the helper methods
async def test_get_merged_village_list(
    state_at_kecamatan_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    user_state = state_at_kecamatan_user_state
    result = await location_flow_handler.get_merged_village_list(
        chat_id=FAKE_CHAT_ID, user_state=user_state
    )
    assert "- cicau" in result
    assert "- sukamahi" in result
    assert "- pasiranji" in result


async def test_get_subdistricts_or_raise_found(
    location_flow_handler: LocationFlowHandler,
) -> None:
    result = await location_flow_handler._get_subdistricts_or_raise(  # pyright: ignore[reportPrivateUsage]
        chat_id=FAKE_CHAT_ID, city_or_regency="kabupaten bekasi"
    )
    assert "cikarang pusat" in result
    assert "cikarang selatan" in result
    assert "serang baru" in result
    assert "setu" in result


async def test_get_subdistricts_or_raise_not_found(
    location_flow_handler: LocationFlowHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(40)  # level: ERROR
    with pytest.raises(DataIntegrityError) as exc_info:
        await location_flow_handler._get_subdistricts_or_raise(  # pyright: ignore[reportPrivateUsage]
            chat_id=FAKE_CHAT_ID,
            city_or_regency="wkwkwkw",  # <- invalid / non-existent
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert "re-input your city or regency" in exc_info.value.message
    assert "subdistrict lookup returned empty" in caplog.messages[0]
    assert "validated city_or_regency: wkwkwkw" in caplog.messages[0]


async def test_get_villages_or_raise_found(
    location_flow_handler: LocationFlowHandler,
) -> None:
    result = await location_flow_handler._get_villages_or_raise(  # pyright: ignore[reportPrivateUsage]
        chat_id=FAKE_CHAT_ID,
        city_or_regency="kabupaten bekasi",
        subdistrict="cikarang pusat",
    )
    assert "cicau" in result
    assert "sukamahi" in result
    assert "pasiranji" in result


async def test_get_villages_or_raise_not_found(
    location_flow_handler: LocationFlowHandler, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(40)  # level: ERROR
    with pytest.raises(DataIntegrityError) as exc_info:
        await location_flow_handler._get_villages_or_raise(  # pyright: ignore[reportPrivateUsage]
            chat_id=FAKE_CHAT_ID,
            city_or_regency="kabupaten bekasi",
            subdistrict="sepatu kw tuh",  # <- invalid / non-existent
        )
    assert exc_info.value.chat_id == FAKE_CHAT_ID
    assert "re-input your city or regency and subdistrict" in exc_info.value.message
    assert "village lookup returned empty" in caplog.messages[0]
    assert "validated city_or_regency: kabupaten bekasi" in caplog.messages[0]
    assert "validated subdistrict: sepatu kw tuh" in caplog.messages[0]


@pytest.mark.parametrize(
    "user_state, should_raise, log_message",
    [
        (None, True, "missing bot_user_state"),
        (_only_chat_id_user_state(), False, None),
        (_state_at_kabupaten_atau_kota_user_state(), False, None),
        (_state_at_kecamatan_user_state(), False, None),
        (_completed_user_state(), False, None),
    ],
)
async def test_get_user_state_or_raise_attr_check_level_none(
    location_flow_handler: LocationFlowHandler,
    user_state: BotUserStateModel | None,
    should_raise: bool,
    log_message: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when the attr_check_level is None"""
    caplog.set_level(40)  # level: ERROR
    if should_raise:
        with pytest.raises(DataIntegrityError):
            location_flow_handler._get_user_state_or_raise(  # pyright: ignore[reportPrivateUsage]
                chat_id=FAKE_CHAT_ID,
                user_state=user_state,
                attr_check_level=None,
            )
        assert log_message is not None
        assert log_message in caplog.messages[0]
    else:
        result = location_flow_handler._get_user_state_or_raise(  # pyright: ignore[reportPrivateUsage]
            chat_id=FAKE_CHAT_ID,
            user_state=user_state,
            attr_check_level=None,
        )
        # compare before and after passed user_state into the method
        assert user_state == result
        # assert no ERROR level logs shows up
        assert not caplog.messages


@pytest.mark.parametrize(
    "user_state, should_raise, log_message",
    [
        (None, True, "missing bot_user_state"),
        (_only_chat_id_user_state(), True, "missing city_or_regency"),
        (_state_at_kabupaten_atau_kota_user_state(), False, None),
        (_state_at_kecamatan_user_state(), False, None),
        (_completed_user_state(), False, None),
    ],
)
async def test_get_user_state_or_raise_attr_check_level_city_or_regency(
    location_flow_handler: LocationFlowHandler,
    user_state: BotUserStateModel | None,
    should_raise: bool,
    log_message: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when the attr_check_level is UserStateCheckLevel.CITY_OR_REGENCY"""
    caplog.set_level(40)  # level: ERROR
    if should_raise:
        with pytest.raises(DataIntegrityError):
            location_flow_handler._get_user_state_or_raise(  # pyright: ignore[reportPrivateUsage]
                chat_id=FAKE_CHAT_ID,
                user_state=user_state,
                attr_check_level=UserStateCheckLevel.CITY_OR_REGENCY,
            )
        assert log_message is not None
        assert log_message in caplog.messages[0]
    else:
        result = location_flow_handler._get_user_state_or_raise(  # pyright: ignore[reportPrivateUsage]
            chat_id=FAKE_CHAT_ID,
            user_state=user_state,
            attr_check_level=UserStateCheckLevel.CITY_OR_REGENCY,
        )
        # compare before and after passed user_state into the method
        assert user_state == result
        # assert no ERROR level logs shows up
        assert not caplog.messages


@pytest.mark.parametrize(
    "user_state, should_raise, log_message",
    [
        (None, True, "missing bot_user_state"),
        (_only_chat_id_user_state(), True, "missing city_or_regency"),
        (_state_at_kabupaten_atau_kota_user_state(), True, "missing subdistrict"),
        (_state_at_kecamatan_user_state(), False, None),
        (_completed_user_state(), False, None),
    ],
)
async def test_get_user_state_or_raise_attr_check_level_subdistrict(
    location_flow_handler: LocationFlowHandler,
    user_state: BotUserStateModel | None,
    should_raise: bool,
    log_message: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when the attr_check_level is UserStateCheckLevel.SUBDISTRICT"""
    caplog.set_level(40)  # level: ERROR
    if should_raise:
        with pytest.raises(DataIntegrityError):
            location_flow_handler._get_user_state_or_raise(  # pyright: ignore[reportPrivateUsage]
                chat_id=FAKE_CHAT_ID,
                user_state=user_state,
                attr_check_level=UserStateCheckLevel.SUBDISTRICT,
            )
        assert log_message is not None
        assert log_message in caplog.messages[0]
    else:
        result = location_flow_handler._get_user_state_or_raise(  # pyright: ignore[reportPrivateUsage]
            chat_id=FAKE_CHAT_ID,
            user_state=user_state,
            attr_check_level=UserStateCheckLevel.SUBDISTRICT,
        )
        # compare before and after passed user_state into the method
        assert user_state == result
        # assert no ERROR level logs shows up
        assert not caplog.messages


@pytest.mark.parametrize(
    "user_state, should_raise, log_message",
    [
        (None, True, "missing bot_user_state"),
        (_only_chat_id_user_state(), True, "missing city_or_regency"),
        (_state_at_kabupaten_atau_kota_user_state(), True, "missing subdistrict"),
        (_state_at_kecamatan_user_state(), True, "missing village"),
        (_completed_user_state(), False, None),
    ],
)
async def test_get_user_state_or_raise_attr_check_level_village(
    location_flow_handler: LocationFlowHandler,
    user_state: BotUserStateModel | None,
    should_raise: bool,
    log_message: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when the attr_check_level is UserStateCheckLevel.VILLAGE"""
    caplog.set_level(40)  # level: ERROR
    if should_raise:
        with pytest.raises(DataIntegrityError):
            location_flow_handler._get_user_state_or_raise(  # pyright: ignore[reportPrivateUsage]
                chat_id=FAKE_CHAT_ID,
                user_state=user_state,
                attr_check_level=UserStateCheckLevel.VILLAGE,
            )
        assert log_message is not None
        assert log_message in caplog.messages[0]
    else:
        result = location_flow_handler._get_user_state_or_raise(  # pyright: ignore[reportPrivateUsage]
            chat_id=FAKE_CHAT_ID,
            user_state=user_state,
            attr_check_level=UserStateCheckLevel.VILLAGE,
        )
        # compare before and after passed user_state into the method
        assert user_state == result
        # assert no ERROR level logs shows up
        assert not caplog.messages


def test_build_flow_result_not_none_user_state(
    state_at_kecamatan_user_state: BotUserStateModel,
    location_flow_handler: LocationFlowHandler,
) -> None:
    result = location_flow_handler._build_flow_result(  # pyright: ignore[reportPrivateUsage]
        state_at_kecamatan_user_state, "message a", "message b", "message c"
    )
    assert isinstance(result, LocationFlowResult)
    assert result.bot_user_state == state_at_kecamatan_user_state
    assert result.message == "message a\n\nmessage b\n\nmessage c"


def test_build_flow_result_none_user_state(
    location_flow_handler: LocationFlowHandler,
) -> None:
    result = location_flow_handler._build_flow_result(  # pyright: ignore[reportPrivateUsage]
        None, "message a", "message b", "message c"
    )
    assert result.bot_user_state is None
    assert result.message == "message a\n\nmessage b\n\nmessage c"


def test_merge_list_multiple_values(location_flow_handler: LocationFlowHandler) -> None:
    result = location_flow_handler._merge_list(["value a", "value b", "value c"])  # pyright: ignore[reportPrivateUsage]
    assert result == "- value a\n- value b\n- value c"


def test_merge_list_single_value(location_flow_handler: LocationFlowHandler) -> None:
    result = location_flow_handler._merge_list(["value a"])  # pyright: ignore[reportPrivateUsage]
    assert result == "- value a"
