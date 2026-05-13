import sqlite3
from unittest.mock import patch

from core.ui.database import show_telemetry


def _build_conn(include_cache_columns: bool):
	conn = sqlite3.connect(":memory:")
	conn.row_factory = sqlite3.Row
	cursor = conn.cursor()
	if include_cache_columns:
		cursor.execute("""
			CREATE TABLE session_telemetry (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				timestamp TEXT,
				duration_s REAL,
				total_tickers INTEGER,
				analyzed_tickers INTEGER,
				cache_hits INTEGER,
				api_attempts INTEGER,
				errors INTEGER
			)
		""")
		cursor.execute("""
			INSERT INTO session_telemetry
				(timestamp, duration_s, total_tickers, analyzed_tickers, cache_hits, api_attempts, errors)
			VALUES
				('2026-01-01 00:00:00', 1.5, 10, 9, 4, 5, 0)
		""")
	else:
		cursor.execute("""
			CREATE TABLE session_telemetry (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				timestamp TEXT,
				duration_s REAL,
				total_tickers INTEGER,
				analyzed_tickers INTEGER
			)
		""")
		cursor.execute("""
			INSERT INTO session_telemetry
				(timestamp, duration_s, total_tickers, analyzed_tickers)
			VALUES
				('2026-01-01 00:00:00', 1.5, 10, 9)
		""")
	conn.commit()
	return conn


def test_show_telemetry_with_cache_columns():
	conn = _build_conn(include_cache_columns=True)
	with patch("core.ui.database.get_db_conn", return_value=conn):
		with patch("core.ui.database.console.print") as mock_print:
			show_telemetry()
	assert mock_print.called


def test_show_telemetry_without_cache_columns():
	conn = _build_conn(include_cache_columns=False)
	with patch("core.ui.database.get_db_conn", return_value=conn):
		with patch("core.ui.database.console.print") as mock_print:
			show_telemetry()
	assert mock_print.called
