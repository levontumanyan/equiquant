"""Unit tests for raw_provider_data repository methods."""

import pytest

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository


@pytest.fixture
def repo(tmp_path):
	"""Provide an isolated temp-file DatabaseRepository."""
	db_manager = DatabaseManager(str(tmp_path / "test.db"))
	return DatabaseRepository(db_manager)


def test_upsert_raw_provider_data_inserts(repo):
	"""Upserting a new record creates a row in raw_provider_data."""
	payload = {"pe_ratio": 25.4, "market_cap": 1_000_000}
	repo.upsert_raw_provider_data("AAPL", "yfinance", payload)

	result = repo.get_raw_provider_data("AAPL", "yfinance")
	assert result is not None
	assert result["provider"] == "yfinance"
	assert result["data"]["pe_ratio"] == 25.4


def test_upsert_raw_provider_data_overwrites(repo):
	"""Second upsert replaces the existing payload for the same symbol/provider."""
	repo.upsert_raw_provider_data("AAPL", "yfinance", {"pe_ratio": 25.4})
	repo.upsert_raw_provider_data("AAPL", "yfinance", {"pe_ratio": 30.0, "eps": 6.1})

	result = repo.get_raw_provider_data("AAPL", "yfinance")
	assert result["data"]["pe_ratio"] == 30.0
	assert result["data"]["eps"] == 6.1


def test_get_raw_provider_data_returns_none_when_missing(repo):
	"""Returns None for a symbol that has no raw data."""
	assert repo.get_raw_provider_data("ZZZZ") is None


def test_get_raw_provider_data_without_provider_returns_latest(repo):
	"""Omitting provider returns the most-recently updated entry."""
	repo.upsert_raw_provider_data("MSFT", "yfinance", {"eps": 9.0})
	repo.upsert_raw_provider_data("MSFT", "other", {"eps": 8.5})

	result = repo.get_raw_provider_data("MSFT")
	assert result is not None
	assert "eps" in result["data"]


def test_multiple_symbols_are_independent(repo):
	"""Different symbols do not interfere with each other."""
	repo.upsert_raw_provider_data("AAPL", "yfinance", {"market_cap": 3e12})
	repo.upsert_raw_provider_data("GOOG", "yfinance", {"market_cap": 2e12})

	aapl = repo.get_raw_provider_data("AAPL", "yfinance")
	goog = repo.get_raw_provider_data("GOOG", "yfinance")
	assert aapl["data"]["market_cap"] == 3e12
	assert goog["data"]["market_cap"] == 2e12


def test_bulk_save_analyses_omits_results_json(repo):
	"""bulk_save_analyses no longer writes results_json to analysis_snapshots."""
	from core.schema import AssetType

	analyses = [
		{
			"symbol": "AAPL",
			"name": "Apple Inc.",
			"asset_type": AssetType.STOCK,
			"sector": "Technology",
			"industry": "Consumer Electronics",
			"score": 72.5,
			"results": [
				{
					"metric": "pe_ratio",
					"raw_value": 25.4,
					"value": 25.4,
					"score": 8.0,
					"weight": 10.0,
				}
			],
		}
	]

	repo.bulk_save_analyses(analyses, "growth")

	conn = repo.db.get_connection()
	cursor = conn.cursor()
	cursor.execute("SELECT results_json FROM analysis_snapshots WHERE symbol = 'AAPL'")
	row = cursor.fetchone()
	assert row is not None
	assert row["results_json"] is None
