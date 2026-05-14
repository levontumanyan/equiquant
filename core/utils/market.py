from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def get_market_calendar(dt: datetime):
	"""
	Returns the most recent market open and close times relative to a given datetime.
	Assumes NYSE/NASDAQ hours: 9:30 AM - 4:00 PM ET.
	"""
	tz = ZoneInfo("America/New_York")
	dt_et = dt.astimezone(tz)

	# Current date in ET
	today = dt_et.date()

	market_open = datetime.combine(today, time(9, 30), tzinfo=tz)
	market_close = datetime.combine(today, time(16, 0), tzinfo=tz)

	return market_open, market_close


def is_market_closed(dt: datetime = None) -> bool:
	"""
	Checks if the market is currently closed.
	"""
	return not is_market_open(dt)


def is_market_open(dt: datetime = None) -> bool:
	"""
	Checks if the market is currently open.
	"""
	if dt is None:
		dt = datetime.now(ZoneInfo("UTC"))

	tz = ZoneInfo("America/New_York")
	dt_et = dt.astimezone(tz)

	# Weekends
	if dt_et.weekday() >= 5:
		return False

	market_open, market_close = get_market_calendar(dt_et)

	return market_open <= dt_et <= market_close


def get_last_market_close(dt: datetime) -> datetime:
	"""
	Returns the most recent market close time prior to the given datetime.
	"""
	tz = ZoneInfo("America/New_York")
	dt_et = dt.astimezone(tz)

	current_day_open, current_day_close = get_market_calendar(dt_et)

	if dt_et > current_day_close:
		# Market closed today
		return current_day_close

	# Market hasn't closed yet today, or is currently open.
	# Last close was yesterday (or Friday if today is Monday)
	days_back = 1
	if dt_et.weekday() == 0:  # Monday
		days_back = 3
	elif dt_et.weekday() == 6:  # Sunday
		days_back = 2

	last_day = dt_et - timedelta(days=days_back)
	_, last_close = get_market_calendar(last_day)
	return last_close
