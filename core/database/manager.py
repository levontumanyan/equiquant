import logging
import sqlite3
from pathlib import Path
from typing import Optional

from core.database.migrations import run_migrations
from core.stats import InstrumentedLock, stats

logger = logging.getLogger(__name__)


class DatabaseManager:
	def __init__(self, db_path: str = "equiquant.db", skip_auto_seed: bool = False):
		"""Initialise the database manager and bring the schema up to date.

		Args:
			db_path: Path to the SQLite database file.
			skip_auto_seed: Skip the auto-seed step (useful in tests that supply their own data).
		"""
		self.db_path = Path(db_path)
		self.conn: Optional[sqlite3.Connection] = None
		self._lock = InstrumentedLock("database_manager", stats)
		self._skip_auto_seed = skip_auto_seed
		self.initialize()

	def initialize(self):
		"""Open the database connection and apply pending schema migrations."""
		with self._lock:
			self.db_path.parent.mkdir(parents=True, exist_ok=True)
			# check_same_thread=False: cross-thread access is allowed because
			# all calls are serialized through self._lock.
			self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
			self.conn.row_factory = sqlite3.Row
			# Enable FK enforcement so CASCADE deletes on portfolios/holdings/
			# transactions work correctly for the lifetime of this connection.
			self.conn.execute("PRAGMA foreign_keys = ON")
			run_migrations(self.conn)
			if not self._skip_auto_seed:
				self._auto_seed()

	def _auto_seed(self):
		"""Seed and synchronize configuration tables.

		Benchmarks and Profiles are ALWAYS synchronized on startup to ensure
		code-level scoring improvements are reflected in the database.
		Other tables (Assets, Groups) are only seeded if empty.
		"""
		from core.database.repository import DatabaseRepository
		from core.database.seeder import DatabaseSeeder

		repo = DatabaseRepository(self)
		seeder = DatabaseSeeder(repo)
		cursor = self.conn.cursor()

		cursor.execute("SELECT COUNT(*) FROM assets")
		if cursor.fetchone()[0] == 0:
			logger.info("Seeding assets and indices...")
			seeder.seed_assets()
			seeder.seed_indices()

		# Always sync benchmarks to apply new logic/thresholds
		logger.info("Synchronizing global benchmarks...")
		seeder.seed_benchmarks()

		# Profiles are only seeded if empty to protect user customizations
		cursor.execute("SELECT COUNT(*) FROM investor_profiles")
		if cursor.fetchone()[0] == 0:
			logger.info("Seeding system profiles...")
			seeder.seed_profiles()

		cursor.execute("SELECT COUNT(*) FROM groups")
		if cursor.fetchone()[0] == 0:
			logger.info("Seeding stock groups...")
			seeder.seed_groups()

		cursor.execute("SELECT COUNT(*) FROM app_settings")
		if cursor.fetchone()[0] == 0:
			logger.info("Seeding application settings...")
			seeder.seed_app_settings()

	def get_connection(self) -> sqlite3.Connection:
		"""Return the DB connection. Serialized access should be managed via DatabaseRepository lock."""
		if self.conn is None:
			self.initialize()
		return self.conn

	def close(self):
		"""Close the database connection."""
		with self._lock:
			if self.conn:
				self.conn.close()
				self.conn = None
