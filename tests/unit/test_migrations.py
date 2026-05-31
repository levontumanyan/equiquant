"""Unit tests for the versioned schema migration runner."""

import sqlite3

from core.database.migrations import _MIGRATIONS_DIR, run_migrations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_conn() -> sqlite3.Connection:
	"""Return an in-memory SQLite connection with FK enforcement enabled."""
	conn = sqlite3.connect(":memory:")
	conn.execute("PRAGMA foreign_keys = ON")
	return conn


def _applied_versions(conn: sqlite3.Connection) -> set:
	"""Return the set of migration versions recorded in schema_migrations."""
	return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def _table_columns(conn: sqlite3.Connection, table: str) -> set:
	"""Return the column names present in *table*."""
	return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


# ---------------------------------------------------------------------------
# schema_migrations bootstrap
# ---------------------------------------------------------------------------


def test_run_migrations_creates_tracking_table():
	"""run_migrations must create schema_migrations on a fresh connection."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)

	tables = {
		r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
	}
	assert "schema_migrations" in tables


def test_run_migrations_records_all_applied_versions():
	"""Every .sql file in migrations/ must appear in schema_migrations after a run."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)

	expected = {p.stem for p in _MIGRATIONS_DIR.glob("*.sql")}
	assert expected == _applied_versions(conn)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_run_migrations_is_idempotent():
	"""Calling run_migrations twice must not raise or duplicate rows."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)
	run_migrations(conn, _MIGRATIONS_DIR)

	versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations")]
	assert len(versions) == len(set(versions)), (
		"Duplicate versions in schema_migrations"
	)


def test_run_migrations_skips_already_applied(tmp_path):
	"""Only pending migrations are executed; applied ones are untouched."""
	conn = _open_conn()
	# Apply first migration only by pre-populating schema_migrations
	conn.execute("""
		CREATE TABLE IF NOT EXISTS schema_migrations (
			version    TEXT PRIMARY KEY,
			applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
		)
	""")
	conn.execute(
		"INSERT INTO schema_migrations (version) VALUES ('0001_initial_schema')"
	)
	conn.commit()

	# Write a minimal single-statement migration to a temp dir
	migrations_tmp = tmp_path / "migrations"
	migrations_tmp.mkdir()
	(migrations_tmp / "0001_initial_schema.sql").write_text(
		"CREATE TABLE should_not_exist (id INTEGER PRIMARY KEY);"
	)
	(migrations_tmp / "0002_new_table.sql").write_text(
		"CREATE TABLE new_table (id INTEGER PRIMARY KEY);"
	)

	run_migrations(conn, migrations_tmp)

	tables = {
		r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
	}
	assert "should_not_exist" not in tables, "Already-applied migration was re-executed"
	assert "new_table" in tables


# ---------------------------------------------------------------------------
# Schema correctness after a full run
# ---------------------------------------------------------------------------


def test_full_schema_creates_all_expected_tables():
	"""After all migrations, every expected table must exist."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)

	tables = {
		r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
	}
	required = {
		"assets",
		"indices",
		"index_constituents",
		"financial_statements",
		"analysis_snapshots",
		"raw_provider_data",
		"document_index",
		"metrics_history",
		"investor_profiles",
		"profile_metric_settings",
		"global_benchmarks",
		"groups",
		"group_constituents",
		"app_settings",
		"sec_cik_mapping",
		"session_telemetry",
		"fx_rates",
		"portfolios",
		"banks",
		"accounts",
		"transactions",
		"portfolio_holdings",
		"schema_migrations",
	}
	missing = required - tables
	assert not missing, f"Tables not created: {missing}"


def test_transactions_has_account_id_column():
	"""transactions must include account_id after migrations."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)
	assert "account_id" in _table_columns(conn, "transactions")


def test_portfolio_holdings_has_account_id_column():
	"""portfolio_holdings must include account_id after migrations."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)
	assert "account_id" in _table_columns(conn, "portfolio_holdings")


def test_app_settings_has_is_secret_column():
	"""app_settings must include is_secret after migrations."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)
	assert "is_secret" in _table_columns(conn, "app_settings")


def test_global_benchmarks_has_is_penalty_column():
	"""global_benchmarks must include is_penalty after migrations."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)
	assert "is_penalty" in _table_columns(conn, "global_benchmarks")


def test_profile_metric_settings_has_is_penalty_column():
	"""profile_metric_settings must include is_penalty after migrations."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)
	assert "is_penalty" in _table_columns(conn, "profile_metric_settings")


def test_profile_weights_table_absent():
	"""Legacy profile_weights table must not exist after migrations."""
	conn = _open_conn()
	run_migrations(conn, _MIGRATIONS_DIR)
	tables = {
		r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
	}
	assert "profile_weights" not in tables


# ---------------------------------------------------------------------------
# Duplicate-column error is handled gracefully
# ---------------------------------------------------------------------------


def test_duplicate_column_migration_marked_as_applied(tmp_path):
	"""A migration that fails with 'duplicate column name' is recorded as applied."""
	conn = _open_conn()
	conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, existing_col TEXT)")
	conn.commit()

	migrations_tmp = tmp_path / "migrations"
	migrations_tmp.mkdir()
	(migrations_tmp / "0001_add_col.sql").write_text(
		"ALTER TABLE t ADD COLUMN existing_col TEXT;"
	)

	run_migrations(conn, migrations_tmp)

	assert "0001_add_col" in _applied_versions(conn)


# ---------------------------------------------------------------------------
# Upgrade path: existing database without schema_migrations
# ---------------------------------------------------------------------------


def test_existing_db_receives_pending_migrations(tmp_path):
	"""A pre-migration database gets all migrations applied on first startup."""
	migrations_tmp = tmp_path / "migrations"
	migrations_tmp.mkdir()
	(migrations_tmp / "0001_create_foo.sql").write_text(
		"CREATE TABLE IF NOT EXISTS foo (id INTEGER PRIMARY KEY);"
	)
	(migrations_tmp / "0002_add_bar.sql").write_text(
		"ALTER TABLE foo ADD COLUMN bar TEXT;"
	)

	conn = _open_conn()
	# Simulate a pre-existing DB: foo exists but no schema_migrations
	conn.execute("CREATE TABLE foo (id INTEGER PRIMARY KEY)")
	conn.commit()

	run_migrations(conn, migrations_tmp)

	assert {"0001_create_foo", "0002_add_bar"} == _applied_versions(conn)
	assert "bar" in _table_columns(conn, "foo")
