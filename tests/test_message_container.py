import pytest

from src.bot.message_container import add_unit, escape_html


class TestEscapeHtml:
    def test_when_value_is_none(self) -> None:
        result = escape_html(value=None)
        assert result is None

    @pytest.mark.parametrize(
        "input_value, expected_return",
        [
            ("<", "&lt;"),
            (">", "&gt;"),
            ("&", "&amp;"),
            ('"', "&quot;"),
            ("'", "&#x27;"),
        ],
    )
    def test_html_characters_escaped(
        self, input_value: str, expected_return: str
    ) -> None:
        result = escape_html(value=input_value)
        assert result == expected_return

    def test_non_html_characters_unchanged(self) -> None:
        result = escape_html(value="fake value")
        assert result == "fake value"

    @pytest.mark.parametrize(
        "input_value, expected_return",
        [
            ("aku<", "aku&lt;"),
            (">kamu", "&gt;kamu"),
            ("aku&kamu", "aku&amp;kamu"),
            ('nama " kamu', "nama &quot; kamu"),
            ("siapa'?", "siapa&#x27;?"),
        ],
    )
    def test_when_html_and_non_html_characters_combined(
        self, input_value: str, expected_return: str
    ) -> None:
        """
        Test that when html and non-html characters combined,
        only the html characters are escaped or changed
        """
        result = escape_html(value=input_value)
        assert result == expected_return


def test_add_unit_when_value_is_none() -> None:
    result = add_unit(value=None, unit="fake unit")
    assert result == "No data"


def test_add_unit_when_value_is_not_none() -> None:
    result = add_unit(value=1, unit="fake unit")
    assert result == "1fake unit"
