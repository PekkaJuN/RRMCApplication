"""The user's local day (archiving spec P1, AC6)."""

from datetime import UTC, date, datetime

from app.local_time import local_today


def test_ac6_late_evening_utc_on_new_years_eve_is_already_next_year_in_finland() -> None:
    def clock() -> datetime:
        return datetime(2025, 12, 31, 22, 30, tzinfo=UTC)

    assert local_today(clock) == date(2026, 1, 1)


def test_ac6_earlier_the_same_utc_day_is_still_the_old_year() -> None:
    def clock() -> datetime:
        return datetime(2025, 12, 31, 21, 30, tzinfo=UTC)

    assert local_today(clock) == date(2025, 12, 31)
