"""
Regression test: DB-based cache writes must not increment stats.cache_hits.

The old file-cache bug counted a ticker as a cache hit even when it was fetched
in the same session. With the DB cache, upsert_raw_provider_data must never
touch stats.cache_hits — only explicit reads (load_cached_data paths) should.
"""

from core.stats import stats


def test_upsert_does_not_increment_cache_hits(tmp_path):
	"""Writing to raw_provider_data must not increment stats.cache_hits."""
	from core.database.manager import DatabaseManager
	from core.database.repository import DatabaseRepository

	db = DatabaseManager(str(tmp_path / "test.db"))
	repo = DatabaseRepository(db)

	stats.cache_hits = 0

	repo.upsert_raw_provider_data(
		"AAPL", "yfinance", {"symbol": "AAPL", "pe_ratio": 25.0}
	)

	assert stats.cache_hits == 0, (
		f"upsert_raw_provider_data must not increment cache_hits, got {stats.cache_hits}"
	)
