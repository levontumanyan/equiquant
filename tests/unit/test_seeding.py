import pytest

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository


@pytest.fixture
def fresh_db(tmp_path):
	"""Provide a DatabaseManager backed by a temp file, auto-seeded."""
	db_path = tmp_path / "test.db"
	manager = DatabaseManager(str(db_path))
	yield manager
	manager.close()


def test_auto_seed_populates_investor_profiles(fresh_db):
	"""Auto-seed must insert at least one investor profile."""
	repo = DatabaseRepository(fresh_db)
	profiles = repo.list_profiles()
	assert len(profiles) > 0, "No investor profiles seeded"


def test_auto_seed_populates_global_benchmarks(fresh_db):
	"""Auto-seed must insert global benchmarks."""
	cursor = fresh_db.get_connection().cursor()
	cursor.execute("SELECT COUNT(*) FROM global_benchmarks")
	count = cursor.fetchone()[0]
	assert count > 0, "No global benchmarks seeded"


def test_auto_seed_populates_sector_benchmarks(fresh_db):
	"""Auto-seed must insert sector benchmarks."""
	cursor = fresh_db.get_connection().cursor()
	cursor.execute("SELECT COUNT(*) FROM sector_benchmarks")
	count = cursor.fetchone()[0]
	assert count > 0, "No sector benchmarks seeded"


def test_auto_seed_populates_stock_groups(fresh_db):
	"""Auto-seed must insert the predefined system groups."""
	repo = DatabaseRepository(fresh_db)
	groups = repo.list_groups()
	names = [g["name"] for g in groups]
	assert "Magnificent 7" in names
	assert "Semiconductors" in names


def test_auto_seed_magnificent_7_constituents(fresh_db):
	"""Magnificent 7 group must have exactly 7 tickers."""
	repo = DatabaseRepository(fresh_db)
	tickers = repo.get_group_constituents("Magnificent 7")
	assert len(tickers) == 7
	assert "AAPL" in tickers
	assert "NVDA" in tickers


def test_auto_seed_idempotent(tmp_path):
	"""Running auto-seed twice must not duplicate rows."""
	from core.database.repository import DatabaseRepository
	from core.database.seeder import DatabaseSeeder

	db_path = tmp_path / "test.db"
	manager = DatabaseManager(str(db_path))
	cursor = manager.get_connection().cursor()

	cursor.execute("SELECT COUNT(*) FROM investor_profiles")
	count_before = cursor.fetchone()[0]

	DatabaseSeeder(DatabaseRepository(manager)).seed_all()

	cursor.execute("SELECT COUNT(*) FROM investor_profiles")
	count_after = cursor.fetchone()[0]

	assert count_after == count_before, "Duplicate rows inserted on second seed"
	manager.close()


def test_group_crud(fresh_db):
	"""upsert_group / update_group_constituents / delete_group round-trip."""
	repo = DatabaseRepository(fresh_db)
	repo.upsert_group("My Watchlist", description="Personal picks", is_system=False)
	repo.update_group_constituents("My Watchlist", ["AAPL", "MSFT"])

	tickers = repo.get_group_constituents("My Watchlist")
	assert set(tickers) == {"AAPL", "MSFT"}

	repo.update_group_constituents("My Watchlist", ["GOOG"])
	tickers = repo.get_group_constituents("My Watchlist")
	assert tickers == ["GOOG"], "update should replace, not append"

	repo.delete_group("My Watchlist")
	groups = [g["name"] for g in repo.list_groups()]
	assert "My Watchlist" not in groups


def test_system_group_not_deletable(fresh_db):
	"""delete_group returns 'system' and leaves the group intact."""
	repo = DatabaseRepository(fresh_db)
	result = repo.delete_group("Magnificent 7")
	assert result == "system"
	groups = [g["name"] for g in repo.list_groups()]
	assert "Magnificent 7" in groups


def test_delete_group_not_found(fresh_db):
	"""delete_group returns 'not_found' for unknown groups."""
	repo = DatabaseRepository(fresh_db)
	result = repo.delete_group("Nonexistent Group")
	assert result == "not_found"


def test_upsert_group_rejects_system_name(fresh_db):
	"""upsert_group raises ValueError when targeting a system group."""
	repo = DatabaseRepository(fresh_db)
	import pytest

	with pytest.raises(ValueError, match="system group"):
		repo.upsert_group("Magnificent 7", description="hijack attempt")
