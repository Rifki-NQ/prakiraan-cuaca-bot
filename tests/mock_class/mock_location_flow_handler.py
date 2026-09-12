from src.models.domain_model import (
    BotUserModel,
    BotUserStateModel,
    LocationFlowResult,
    LocationFlowResultComplete,
)
from src.exceptions import DataIntegrityError

FAKE_BOT_USER_STATE = BotUserStateModel(chat_id=1)


class MockLocationFlowHandlerNoError:
    async def handle_input_for_city_or_regency(
        self, chat_id: int, city_or_regency: str
    ) -> LocationFlowResult:
        return LocationFlowResult(
            bot_user_state=FAKE_BOT_USER_STATE, message="fake flow result"
        )

    async def handle_input_for_subdistrict(
        self,
        chat_id: int,
        user_state: BotUserStateModel | None,
        subdistrict: str,
    ) -> LocationFlowResult:
        return LocationFlowResult(
            bot_user_state=FAKE_BOT_USER_STATE, message="fake flow result"
        )

    async def handle_input_for_village(
        self, chat_id: int, user_state: BotUserStateModel | None, village: str
    ) -> LocationFlowResult | LocationFlowResultComplete:
        """
        if chat_id = 0, return LocationFlowResult, otherwise
        return LocationFlowResultComplete.
        """
        if chat_id == 0:
            return LocationFlowResult(
                bot_user_state=FAKE_BOT_USER_STATE, message="fake flow result"
            )
        else:
            return LocationFlowResultComplete(
                bot_user_state=FAKE_BOT_USER_STATE,
                adm4_code="fake_adm4_code",
                message="fake complete flow result",
            )

    async def revert_location_state(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> LocationFlowResult:
        return LocationFlowResult(
            bot_user_state=FAKE_BOT_USER_STATE, message="fake flow result"
        )

    async def get_full_address(
        self, chat_id: int, user_data: BotUserModel | None
    ) -> str:
        return "fake address"

    async def get_adm4_code_or_raise(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> str:
        return "fake adm4_code"

    async def get_merged_subdistrict_list(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> str:
        return "fake merged subdistrict list"

    async def get_merged_village_list(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> str:
        return "fake merged village list"


class MockLocationFlowHandlerWithError:
    async def handle_input_for_city_or_regency(
        self, chat_id: int, city_or_regency: str
    ) -> LocationFlowResult:
        raise DataIntegrityError(1, "fake error")

    async def handle_input_for_subdistrict(
        self,
        chat_id: int,
        user_state: BotUserStateModel | None,
        subdistrict: str,
    ) -> LocationFlowResult:
        raise DataIntegrityError(1, "fake error")

    async def handle_input_for_village(
        self, chat_id: int, user_state: BotUserStateModel | None, village: str
    ) -> LocationFlowResult | LocationFlowResultComplete:
        raise DataIntegrityError(1, "fake error")

    async def revert_location_state(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> LocationFlowResult:
        raise DataIntegrityError(1, "fake error")

    async def get_full_address(
        self, chat_id: int, user_data: BotUserModel | None
    ) -> str:
        raise DataIntegrityError(1, "fake error")

    async def get_adm4_code_or_raise(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> str:
        raise DataIntegrityError(1, "fake error")

    async def get_merged_subdistrict_list(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> str:
        raise DataIntegrityError(1, "fake error")

    async def get_merged_village_list(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> str:
        raise DataIntegrityError(1, "fake error")
