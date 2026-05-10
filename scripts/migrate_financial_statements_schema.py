import logging
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_financial_statements():
	conn = sqlite3.connect("market_analysis.db")
	cursor = conn.cursor()

	try:
		logger.info("Starting migration for financial_statements table...")

		# 1. Create a temporary table with the new schema
		cursor.execute("""
            CREATE TABLE financial_statements_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                statement_type TEXT,
                period_type TEXT,
                fiscal_date DATE,
                metric_key TEXT,
                value REAL,
                FOREIGN KEY (symbol) REFERENCES assets(symbol),
                UNIQUE(symbol, statement_type, period_type, fiscal_date, metric_key)
            )
        """)

		# 2. Copy data, ignoring or replacing duplicates
		# We use INSERT OR REPLACE to handle any existing duplicates in the old data
		cursor.execute("""
            INSERT OR REPLACE INTO financial_statements_new (
                id, symbol, statement_type, period_type, fiscal_date, metric_key, value
            )
            SELECT id, symbol, statement_type, period_type, fiscal_date, metric_key, value
            FROM financial_statements
        """)

		# 3. Drop the old table
		cursor.execute("DROP TABLE financial_statements")

		# 4. Rename the new table
		cursor.execute(
			"ALTER TABLE financial_statements_new RENAME TO financial_statements"
		)

		conn.commit()
		logger.info(
			"Migration successful: Added UNIQUE constraint to financial_statements."
		)

	except sqlite3.Error as e:
		conn.rollback()
		logger.error(f"Migration failed: {e}")
	finally:
		conn.close()


if __name__ == "__main__":
	migrate_financial_statements()
