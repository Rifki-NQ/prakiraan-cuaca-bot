import logging
from typing import NoReturn
from src.bot import message_container
from src.models.domain_model import (
    LocationFlowResult,
    LocationFlowResultComplete,
    BotUserModel,
    BotUserStateModel,
)
from src.models.protocols import LocationFinderProtocol
from src.exceptions import (
    EmptyQueryResultError,
    EmptyInputValueError,
    DataIntegrityError,
)

logger = logging.getLogger(__name__)


class LocationFlowHandler:
    """Handles location lookup logic flow."""

    def __init__(self, location_finder: LocationFinderProtocol) -> None:
        self.location_finder = location_finder

    async def handle_input_for_city_or_regency(
        self, chat_id: int, city_or_regency: str | None
    ) -> LocationFlowResult:
        city_or_regency = self._get_value_or_raise(chat_id, city_or_regency)
        try:
            result = await self.location_finder.search_city_or_regency(city_or_regency)
        except EmptyQueryResultError as e:
            return LocationFlowResult(
                message=message_container.notify_city_or_regency_not_found(
                    e.query.get("city_or_regency")
                )
            )
        if len(result) == 1:
            subdistricts = await self._get_subdistricts_or_raise(chat_id, result[0])
            return LocationFlowResult(
                message=self._merge_messages(
                    message_container.notify_city_or_regency_updated(result[0]),
                    # immediately proceed to show list of the subdistricts
                    message_container.notify_to_choose_subdistrict(
                        self._merge_list(subdistricts)
                    ),
                ),
                bot_user_state=BotUserStateModel(
                    chat_id=chat_id, kabupaten_atau_kota=result[0]
                ),
            )
        return LocationFlowResult(
            message=message_container.notify_to_choose_city_or_regency(
                self._merge_list(result)
            )
        )

    async def handle_input_for_subdistrict(
        self,
        chat_id: int,
        user_state: BotUserStateModel | None,
        subdistrict: str | None,
    ) -> LocationFlowResult:
        subdistrict = self._get_value_or_raise(chat_id, subdistrict)
        if user_state is None:
            logger.error(
                f"Unexpected: missing bot_user_state data for chat_id: {chat_id}"
            )
            self._raise_data_integrity_error(chat_id, "city_or_regency")
        elif user_state.kabupaten_atau_kota is None:
            logger.error(
                f"Unexpected: missing city_or_regency data from bot_user_state table for chat_id: {chat_id}"
            )
            self._raise_data_integrity_error(chat_id, "city_or_regency")
        subdistricts = await self._get_subdistricts_or_raise(
            chat_id, user_state.kabupaten_atau_kota
        )
        # check whether user inputted value exists in the query result
        if subdistrict in subdistricts:
            villages = await self._get_villages_or_raise(
                chat_id, user_state.kabupaten_atau_kota, subdistrict
            )
            return LocationFlowResult(
                message=self._merge_messages(
                    message_container.notify_subdistrict_updated(subdistrict),
                    # immediately proceed to show list of the villages
                    message_container.notify_to_choose_village(
                        self._merge_list(villages)
                    ),
                ),
                bot_user_state=BotUserStateModel(
                    chat_id=chat_id,
                    kabupaten_atau_kota=user_state.kabupaten_atau_kota,
                    kecamatan=subdistrict,
                ),
            )
        return LocationFlowResult(
            message=message_container.notify_subdistrict_not_found(
                subdistrict, self._merge_list(subdistricts)
            )
        )

    async def handle_input_for_village(
        self, chat_id: int, user_state: BotUserStateModel | None, village: str | None
    ) -> LocationFlowResult | LocationFlowResultComplete:
        village = self._get_value_or_raise(chat_id, village)
        if user_state is None:
            logger.error(
                f"Unexpected: missing bot_user_state data for chat_id: {chat_id}"
            )
            self._raise_data_integrity_error(chat_id, "city_or_regency")
        elif user_state.kabupaten_atau_kota is None:
            logger.error(
                f"Unexpected: missing city_or_regency data from bot_user_state table for chat_id: {chat_id}"
            )
            self._raise_data_integrity_error(chat_id, "city_or_regency")
        elif user_state.kecamatan is None:
            logger.error(
                f"Unexpected: missing subdistrict data from bot_user_state table for chat_id: {chat_id}"
            )
            self._raise_data_integrity_error(chat_id, "subdistrict")
        villages = await self._get_villages_or_raise(
            chat_id, user_state.kabupaten_atau_kota, user_state.kecamatan
        )
        if village in villages:
            # immediately get adm4_code based on the full address
            adm4_code = await self._get_adm4_code_or_raise(
                chat_id, user_state.kabupaten_atau_kota, user_state.kecamatan, village
            )
            return LocationFlowResultComplete(
                message=self._merge_messages(
                    message_container.notify_village_updated(village),
                    message_container.notify_location_updated(
                        user_state.kabupaten_atau_kota,
                        user_state.kecamatan,
                        village,
                        adm4_code,
                    ),
                ),
                bot_user_state=BotUserStateModel(
                    chat_id=chat_id,
                    kabupaten_atau_kota=user_state.kabupaten_atau_kota,
                    kecamatan=user_state.kecamatan,
                    desa_atau_kelurahan=village,
                ),
                adm4_code=adm4_code,
            )
        return LocationFlowResult(
            message=message_container.notify_village_not_found(
                village, self._merge_list(villages)
            )
        )

    async def get_full_address(
        self, chat_id: int, user_data: BotUserModel | None
    ) -> str:
        if user_data is None:
            logger.error("Unexpected: missing bot_user data from the database")
            self._raise_data_integrity_error(chat_id, "entire")
        if user_data.adm4_code is None:
            logger.error("Unexpected: missing adm4_code from the bot_user table")
            self._raise_data_integrity_error(chat_id, "entire")
        try:
            address = await self.location_finder.get_full_address(user_data.adm4_code)
            return message_container.show_user_full_address(
                city_or_regency=address.kabupaten_atau_kota,
                subdistrict=address.kecamatan,
                village=address.desa_atau_kelurahan,
                adm4_code=address.kode_adm4,
            )
        except EmptyQueryResultError as e:
            logger.error(f"Unexpected: no address found for the adm4_code: {e}")
            self._raise_data_integrity_error(chat_id, "entire")

    async def _get_subdistricts_or_raise(
        self, chat_id: int, city_or_regency: str
    ) -> list[str]:
        try:
            return await self.location_finder.search_subdistrict(city_or_regency)
        except EmptyQueryResultError as e:
            logger.error(
                "Unexpected: subdistrict lookup returned empty result\n"
                f"for validated city_or_regency: {e.query.get('city_or_regency')}"
            )
            self._raise_data_integrity_error(chat_id, "city_or_regency")

    async def _get_villages_or_raise(
        self, chat_id: int, city_or_regency: str, subdistrict: str
    ) -> list[str]:
        try:
            return await self.location_finder.search_village(
                city_or_regency, subdistrict
            )
        except EmptyQueryResultError as e:
            logger.error(
                "Unexpected: village lookup returned empty result\n"
                f"for validated city_or_regency: {e.query.get('city_or_regency')}, "
                f"and validated subdistrict: {e.query.get('subdistrict')}"
            )
            self._raise_data_integrity_error(chat_id, "city_or_regency and subdistrict")

    async def _get_adm4_code_or_raise(
        self, chat_id: int, city_or_regency: str, subdistrict: str, village: str
    ) -> str:
        try:
            return await self.location_finder.get_adm4_code(
                city_or_regency, subdistrict, village
            )
        except EmptyQueryResultError as e:
            logger.error(
                "Unexpected: adm4_code lookup returned empty result\n"
                f"for validated city_or_regency: {e.query.get('city_or_regency')}, "
                f"and validated subdistrict: {e.query.get('subdistrict')}, "
                f"and validate village: {e.query.get('village')}"
            )
            self._raise_data_integrity_error(chat_id, "entire")

    def _merge_list(self, list_value: list[str]) -> str:
        """
        Merge given list of values into a single string.

        example: ["satu", "dua", "tiga"]
        is converted into:
        - satu
        - dua
        - tiga
        """
        return "\n".join(["- " + ls for ls in list_value])

    def _merge_messages(self, *messages: str) -> str:
        """Merge given string tuple into a single string."""
        return "\n".join(messages)

    def _get_value_or_raise(self, chat_id: int, input_value: str | None) -> str:
        if input_value is None:
            raise EmptyInputValueError(
                chat_id, "Error: input value is required after /input command"
            )
        return input_value

    def _raise_data_integrity_error(
        self, chat_id: int, re_enter_value: str
    ) -> NoReturn:
        """
        raise DataIntegrityError with additional information
        about what to re-input to user.
        """
        raise DataIntegrityError(
            chat_id,
            f"Error: system failure occured, please re-input your {re_enter_value} location",
        )
