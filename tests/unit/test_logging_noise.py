"""
Cache logging regression: should_use_db_cache must not log false cache hits
for tickers that were written to raw_provider_data in the same session.
"""

from core.stats import stats


def test_db_cache_hit_does_not_double_count(tmp_path):
	"""
	should_use_db_cache returning True must not increment stats.cache_hits
	on its own — only explicit read paths (get_cached_stock_data) should.
	"""
	from core.database.manager import DatabaseManager
	from core.database.repository import DatabaseRepository

	db = DatabaseManager(str(tmp_path / "test.db"))
	repo = DatabaseRepository(db)

	repo.upsert_raw_provider_data("AAPL", "yfinance", {"symbol": "AAPL"})

	stats.cache_hits = 0

	# TTL check should not increment cache_hits
	repo.should_use_db_cache("AAPL")

	assert stats.cache_hits == 0
