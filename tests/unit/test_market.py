from datetime import datetime
from zoneinfo import ZoneInfo

from core.utils.market import get_last_market_close, is_market_closed


def test_is_market_closed():
	# Wednesday at 2 PM ET (Open)
	dt_open = datetime(2026, 4, 29, 14, 0, tzinfo=ZoneInfo("America/New_York"))
	assert not is_market_closed(dt_open)

	# Wednesday at 11 PM ET (Closed)
	dt_closed = datetime(2026, 4, 29, 23, 0, tzinfo=ZoneInfo("America/New_York"))
	assert is_market_closed(dt_closed)

	# Saturday (Closed)
	dt_weekend = datetime(2026, 5, 2, 12, 0, tzinfo=ZoneInfo("America/New_York"))
	assert is_market_closed(dt_weekend)


def test_get_last_market_close():
	# Monday before open (Last close should be Friday)
	dt_monday_morning = datetime(2026, 4, 27, 8, 0, tzinfo=ZoneInfo("America/New_York"))
	last_close = get_last_market_close(dt_monday_morning)
	assert last_close.weekday() == 4  # Friday
	assert last_close.hour == 16

	# Monday after close (Last close should be today)
	dt_monday_night = datetime(2026, 4, 27, 20, 0, tzinfo=ZoneInfo("America/New_York"))
	last_close = get_last_market_close(dt_monday_night)
	assert last_close.day == 27
	assert last_close.hour == 16
