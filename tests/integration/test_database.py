import sqlite3
from datetime import datetime, timedelta

import pytest

from core.analysis.indices import get_index_components
from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository


@pytest.fixture
def db_manager(tmp_path):
	db_file = tmp_path / "test_market.db"
	manager = DatabaseManager(str(db_file))
	yield manager
	manager.close()


def test_database_initialization(db_manager):
	"""Test that the database is created and tables exist."""
	conn = db_manager.get_connection()
	cursor = conn.cursor()

	# Check for tables
	cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
	tables = {row[0] for row in cursor.fetchall()}

	expected_tables = {
		"assets",
		"indices",
		"index_constituents",
		"financial_statements",
		"analysis_snapshots",
		"document_index",
		"sqlite_sequence",  # Created for autoincrement
	}

	for table in expected_tables:
		assert table in tables or table == "sqlite_sequence"


def test_index_staleness(db_manager):
	"""Test that stale index data in DB triggers a refresh."""
	repo = DatabaseRepository(db_manager)
	symbol = "STALE_INDEX"

	# 1. Insert stale data (10 days old)
	conn = db_manager.get_connection()
	stale_date = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
	conn.execute(
		"INSERT INTO indices (symbol, name, last_updated) VALUES (?, ?, ?)",
		(symbol, "Stale Index", stale_date),
	)
	conn.execute(
		"INSERT INTO index_constituents (index_symbol, asset_symbol) VALUES (?, ?)",
		(symbol, "OLD_TICKER"),
	)
	conn.commit()

	# 2. Call get_index_components - should see it's stale and return [symbol] (fallback)
	# because it's not a real index, but it SHOULD NOT return "OLD_TICKER"
	components = get_index_components(symbol, repo=repo)

	assert "OLD_TICKER" not in components
	assert symbol in components  # Fallback for non-existent index

	# 3. Verify DB was updated with new date
	index_meta = repo.get_index(symbol)
	last_updated = datetime.strptime(index_meta["last_updated"], "%Y-%m-%d %H:%M:%S")
	assert (datetime.utcnow() - last_updated) < timedelta(seconds=10)


def test_index_freshness(db_manager):
	"""Test that fresh index data in DB is returned directly."""
	repo = DatabaseRepository(db_manager)
	symbol = "FRESH_INDEX"

	# 1. Insert fresh data
	repo.upsert_index(symbol, "Fresh Index")
	repo.update_index_constituents(symbol, ["FRESH_TICKER"])

	# 2. Call get_index_components
	components = get_index_components(symbol, repo=repo)

	assert components == ["FRESH_TICKER"]


def test_foreign_key_constraints(db_manager):
	"""Test that foreign keys are working (requires PRAGMA)."""
	conn = db_manager.get_connection()
	# Enable FK
	conn.execute("PRAGMA foreign_keys = ON;")
	cursor = conn.cursor()

	# Try to insert into index_constituents without asset or index existing
	# Note: In SQLite, index_constituents primary key (index_symbol, asset_symbol)
	# might succeed if NOT NULL isn't violated, but we want to check FK
	with pytest.raises(sqlite3.IntegrityError):
		cursor.execute(
			"INSERT INTO index_constituents (index_symbol, asset_symbol) VALUES ('SP500', 'AAPL');"
		)


def test_historical_scores(db_manager):
	"""Test creating and retrieving historical analysis snapshots."""
	import time

	repo = DatabaseRepository(db_manager)
	symbol = "TEST_STOCK"
	profile = "growth"

	# Create some snapshots
	repo.create_analysis_snapshot(symbol, profile, 75.0, '{"result": "good"}')
	time.sleep(1.1)  # Ensure different timestamp (second precision)
	repo.create_analysis_snapshot(symbol, profile, 80.0, '{"result": "better"}')

	# Retrieve snapshots
	history = repo.get_historical_scores(symbol, profile)

	assert len(history) == 2
	assert history[0]["total_score"] == 80.0
	assert history[1]["total_score"] == 75.0
	assert "timestamp" in history[0]
