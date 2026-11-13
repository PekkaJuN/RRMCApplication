"""The user's time zone, shared by the PDF export and archiving (archiving spec P1)."""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

# The user's time zone: a file made just after midnight in Finland gets that day, and a year
# is finished only when it has ended in Finland.
LOCAL_TIME = ZoneInfo("Europe/Helsinki")


def local_today(clock: Callable[[], datetime]) -> date:
    return clock().astimezone(LOCAL_TIME).date()
