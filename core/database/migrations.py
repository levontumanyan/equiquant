import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations(
	conn: sqlite3.Connection, migrations_dir: Path = _MIGRATIONS_DIR
) -> None:
	"""Apply all pending numbered SQL migrations in version order.

	Maintains a `schema_migrations` table to track which migration files have
	already been applied, so each file is executed at most once regardless of
	how many times the application restarts.

	Args:
		conn: An open SQLite connection. FK enforcement and PRAGMAs must already be set.
		migrations_dir: Directory containing ``NNNN_description.sql`` files.
			Defaults to the ``migrations/`` sub-package next to this module.

	Returns:
		None. Raises ``sqlite3.OperationalError`` on unexpected SQL failures.
	"""
	conn.execute("""
		CREATE TABLE IF NOT EXISTS schema_migrations (
			version     TEXT PRIMARY KEY,
			applied_at  DATETIME DEFAULT CURRENT_TIMESTAMP
		)
	""")
	conn.commit()

	applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

	for path in sorted(migrations_dir.glob("*.sql")):
		version = path.stem
		if version in applied:
			continue

		sql = path.read_text()
		try:
			conn.executescript(sql)
		except sqlite3.OperationalError as exc:
			if "duplicate column name" in str(exc):
				# Column was added by a prior ad-hoc migration; idempotent.
				logger.warning(
					"Migration %s: %s — already applied, marking as done", version, exc
				)
			else:
				raise

		conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
		conn.commit()
		logger.info("Applied migration: %s", version)
