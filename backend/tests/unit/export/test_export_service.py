"""The `weeks` value of the comparison CSV file (comparison CSV export spec PC8, P5)."""

import pytest

from app.errors import AppError
from app.export.service import parse_weeks


@pytest.mark.parametrize(("value", "weeks"), [(None, False), ("false", False), ("true", True)])
def test_ac2_ac3_weeks_values(value: str | None, weeks: bool) -> None:
    assert parse_weeks(value) is weeks


@pytest.mark.parametrize("value", ["yes", "True", "1", ""])
def test_ac11_other_weeks_values_are_invalid_requests(value: str) -> None:
    with pytest.raises(AppError) as raised:
        parse_weeks(value)

    assert (raised.value.code, raised.value.status) == ("invalid_request", 422)
