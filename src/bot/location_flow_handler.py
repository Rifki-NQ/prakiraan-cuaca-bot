import logging

from src.bot import message_container
from src.bot.bot_utils import (
    get_user_data_or_raise,
    merge_messages,
    raise_data_integrity_error,
)
from src.exceptions import (
    EmptyQueryResultError,
)
from src.models.domain_model import (
    BotUserModel,
    BotUserStateModel,
    LocationFlowResult,
    LocationFlowResultComplete,
)
from src.models.enums import UserStateCheckLevel
from src.models.protocols import LocationFinderProtocol

logger = logging.getLogger(__name__)


class LocationFlowHandler:
    """Handles location lookup logic flow."""

    def __init__(self, location_finder: LocationFinderProtocol) -> None:
        self.location_finder = location_finder

    async def handle_input_for_city_or_regency(
        self, chat_id: int, city_or_regency: str
    ) -> LocationFlowResult:
        try:
            result = await self.location_finder.search_city_or_regency(city_or_regency)
        except EmptyQueryResultError as e:
            return LocationFlowResult(
                message=message_container.notify_city_or_regency_not_found(
                    e.query.get("city_or_regency")
                )
            )
        matched = self._find_match(city_or_regency, result)
        if matched:
            user_state = BotUserStateModel(chat_id, matched)
            return self._build_flow_result(
                user_state,
                message_container.notify_city_or_regency_updated(matched),
                message_container.notify_to_choose_subdistrict(
                    await self.get_merged_subdistrict_list(chat_id, user_state)
                ),
            )
        return self._build_flow_result(
            None,
            message_container.notify_to_choose_city_or_regency(
                self._merge_list(result)
            ),
        )

    async def handle_input_for_subdistrict(
        self,
        chat_id: int,
        user_state: BotUserStateModel | None,
        subdistrict: str,
    ) -> LocationFlowResult:
        user_state = self._get_user_state_or_raise(
            chat_id, user_state, UserStateCheckLevel.CITY_OR_REGENCY
        )
        assert user_state.kabupaten_atau_kota is not None, (
            "_get_user_state_or_raise() guarantee this attribute is not None"
        )
        subdistricts = await self._get_subdistricts_or_raise(
            chat_id, user_state.kabupaten_atau_kota
        )
        matched = self._find_match(subdistrict, subdistricts)
        if matched:
            new_user_state = BotUserStateModel(
                chat_id, user_state.kabupaten_atau_kota, matched
            )
            return self._build_flow_result(
                new_user_state,
                message_container.notify_subdistrict_updated(matched),
                message_container.notify_to_choose_village(
                    await self.get_merged_village_list(chat_id, new_user_state)
                ),
            )
        return self._build_flow_result(
            None,
            message_container.notify_subdistrict_not_found(
                subdistrict, self._merge_list(subdistricts)
            ),
        )

    async def handle_input_for_village(
        self, chat_id: int, user_state: BotUserStateModel | None, village: str
    ) -> LocationFlowResult | LocationFlowResultComplete:
        user_state = self._get_user_state_or_raise(
            chat_id, user_state, UserStateCheckLevel.SUBDISTRICT
        )
        assert user_state.kabupaten_atau_kota is not None, (
            "_get_user_state_or_raise() guarantee this attribute is not None"
        )
        assert user_state.kecamatan is not None, (
            "_get_user_state_or_raise() guarantee this attribute is not None"
        )
        villages = await self._get_villages_or_raise(
            chat_id, user_state.kabupaten_atau_kota, user_state.kecamatan
        )
        matched = self._find_match(village, villages)
        if matched:
            new_user_state = BotUserStateModel(
                chat_id, user_state.kabupaten_atau_kota, user_state.kecamatan, matched
            )
            # immediately get the adm4_code based on the full address
            adm4_code = await self.get_adm4_code_or_raise(chat_id, new_user_state)
            return LocationFlowResultComplete(
                message=merge_messages(
                    message_container.notify_village_updated(matched),
                    message_container.notify_location_updated(
                        new_user_state,
                        adm4_code,
                    ),
                ),
                bot_user_state=new_user_state,
                adm4_code=adm4_code,
            )
        return self._build_flow_result(
            None,
            message_container.notify_village_not_found(
                village, self._merge_list(villages)
            ),
        )

    async def revert_location_state(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> LocationFlowResult:
        """
        Revert the user_state by clearing the most specific (lowest-level) not-None attr,
        clears desa_atau_kelurahan first if set, then kecamatan, then kabupaten_atau_kota.
        """
        user_state = self._get_user_state_or_raise(chat_id, user_state)
        if user_state.desa_atau_kelurahan is not None:
            user_state.desa_atau_kelurahan = None
            return self._build_flow_result(
                user_state,
                message_container.show_revert_message("village"),
                message_container.notify_to_choose_village(
                    await self.get_merged_village_list(chat_id, user_state)
                ),
            )
        elif user_state.kecamatan is not None:
            user_state.kecamatan = None
            return self._build_flow_result(
                user_state,
                message_container.show_revert_message("subdistrict"),
                message_container.notify_to_choose_subdistrict(
                    await self.get_merged_subdistrict_list(chat_id, user_state)
                ),
            )
        elif user_state.kabupaten_atau_kota is not None:
            user_state.kabupaten_atau_kota = None
            return self._build_flow_result(
                user_state,
                message_container.show_revert_message("city or regency"),
                message_container.ASK_CITY_OR_REGENCY,
            )
        # this is reachable in a case where user has a state data in the db
        # but the row values are all null or None (except the row timestamps)
        return self._build_flow_result(
            user_state, message_container.ASK_CITY_OR_REGENCY
        )

    async def get_full_address(
        self, chat_id: int, user_data: BotUserModel | None
    ) -> str:
        user_data = get_user_data_or_raise(chat_id, user_data, logger)
        assert user_data.adm4_code is not None, (
            "get_user_data_or_raise() guarantee this attribute is not None"
        )
        try:
            address = await self.location_finder.get_full_address(user_data.adm4_code)
            return message_container.show_user_full_address(
                city_or_regency=address.kabupaten_atau_kota,
                subdistrict=address.kecamatan,
                village=address.desa_atau_kelurahan,
                adm4_code=address.kode_adm4,
            )
        except EmptyQueryResultError as e:
            logger.error(
                f"Unexpected: no address found for the adm4_code: {e.query.get('adm4_code')}"
            )
            raise_data_integrity_error(chat_id, "entire")

    async def get_adm4_code_or_raise(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> str:
        user_state = self._get_user_state_or_raise(
            chat_id, user_state, UserStateCheckLevel.VILLAGE
        )
        assert user_state.kabupaten_atau_kota is not None, (
            "_get_user_state_or_raise() guarantee this attribute is not None"
        )
        assert user_state.kecamatan is not None, (
            "_get_user_state_or_raise() guarantee this attribute is not None"
        )
        assert user_state.desa_atau_kelurahan is not None, (
            "_get_user_state_or_raise() guarantee this attribute is not None"
        )
        try:
            return await self.location_finder.get_adm4_code(
                user_state.kabupaten_atau_kota,
                user_state.kecamatan,
                user_state.desa_atau_kelurahan,
            )
        except EmptyQueryResultError as e:
            logger.error(
                "Unexpected: adm4_code lookup returned empty result\n"
                f"for validated city_or_regency: {e.query.get('city_or_regency')}, "
                f"and validated subdistrict: {e.query.get('subdistrict')}, "
                f"and validated village: {e.query.get('village')}"
            )
            raise_data_integrity_error(chat_id, "entire")

    async def get_merged_subdistrict_list(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> str:
        """Return a merged list of subdistricts."""
        # reason why user_state instead of direct kabupaten_atau_kota:
        # because this method is also meant to be called outside of this class
        user_state = self._get_user_state_or_raise(
            chat_id, user_state, UserStateCheckLevel.CITY_OR_REGENCY
        )
        assert user_state.kabupaten_atau_kota is not None, (
            "_get_user_state_or_raise() guarantee this attribute is not None"
        )
        subdistricts = await self._get_subdistricts_or_raise(
            chat_id, user_state.kabupaten_atau_kota
        )
        return self._merge_list(subdistricts)

    async def get_merged_village_list(
        self, chat_id: int, user_state: BotUserStateModel | None
    ) -> str:
        """Return a merged list of villages"""
        # same reason for not direct kabupaten_atau_kota and kecamatan params
        # with get_merged_subdistrict_list()
        user_state = self._get_user_state_or_raise(
            chat_id, user_state, UserStateCheckLevel.SUBDISTRICT
        )
        assert user_state.kabupaten_atau_kota is not None, (
            "_get_user_state_or_raise() guarantee this attribute is not None"
        )
        assert user_state.kecamatan is not None, (
            "_get_user_state_or_raise() guarantee this attribute is not None"
        )
        villages = await self._get_villages_or_raise(
            chat_id, user_state.kabupaten_atau_kota, user_state.kecamatan
        )
        return self._merge_list(villages)

    async def _get_subdistricts_or_raise(
        self, chat_id: int, city_or_regency: str
    ) -> list[str]:
        """Return list of subdistricts, raise error if not found."""
        try:
            return await self.location_finder.search_subdistrict(city_or_regency)
        except EmptyQueryResultError as e:
            logger.error(
                "Unexpected: subdistrict lookup returned empty result\n"
                f"for validated city_or_regency: {e.query.get('city_or_regency')}"
            )
            raise_data_integrity_error(chat_id, "city or regency")

    async def _get_villages_or_raise(
        self, chat_id: int, city_or_regency: str, subdistrict: str
    ) -> list[str]:
        """Return list of villages, raise error if not found."""
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
            raise_data_integrity_error(chat_id, "city or regency and subdistrict")

    # TODO: make different dataclass with different Optional fields after
    #       filtering it on this method to avoid duplicated, unnecessary assert obj.attr
    def _get_user_state_or_raise(
        self,
        chat_id: int,
        user_state: BotUserStateModel | None,
        attr_check_level: UserStateCheckLevel | None = None,
    ) -> BotUserStateModel:
        """
        get the state of a user,
        raise DataIntegrityError immediately if the user_state is None
        """
        if user_state is None:
            logger.error(
                f"Unexpected: missing bot_user_state data for chat_id: {chat_id}"
            )
            raise_data_integrity_error(chat_id, "city or regency")
        if attr_check_level is None:
            return user_state
        if (
            user_state.kabupaten_atau_kota is None
            and attr_check_level >= UserStateCheckLevel.CITY_OR_REGENCY
        ):
            logger.error(
                f"Unexpected: missing city_or_regency data from bot_user_state table for chat_id: {chat_id}"
            )
            raise_data_integrity_error(chat_id, "city or regency")
        if (
            user_state.kecamatan is None
            and attr_check_level >= UserStateCheckLevel.SUBDISTRICT
        ):
            logger.error(
                f"Unexpected: missing subdistrict data from bot_user_state table for chat_id: {chat_id}"
            )
            raise_data_integrity_error(chat_id, "city or regency and subdistrict")
        if (
            user_state.desa_atau_kelurahan is None
            and attr_check_level >= UserStateCheckLevel.VILLAGE
        ):
            logger.error(
                f"Unexpected: missing village data from bot_user_state table for chat_id: {chat_id}"
            )
            raise_data_integrity_error(chat_id, "entire")
        return user_state

    def _build_flow_result(
        self, user_state: BotUserStateModel | None, *messages: str
    ) -> LocationFlowResult:
        return LocationFlowResult(
            message=merge_messages(*messages), bot_user_state=user_state
        )

    def _find_match(self, user_input: str, query_result: list[str]) -> str | None:
        """
        Return the first query_result immediately if the length is 1,
        if the length is not 1, iterate over the query_result and
        do case-insensitive comparison until there is a match,
        return None if both is failed to find a match.
        """
        if len(query_result) == 1:
            return query_result[0]
        for result in query_result:
            if user_input.lower() == result.lower():
                return result  # return the non-lowered result
        return None

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
