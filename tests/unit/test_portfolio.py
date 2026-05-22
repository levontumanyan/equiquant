"""Unit tests for multi-portfolio management (DB layer)."""

import pytest

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository


@pytest.fixture
def repo(tmp_path):
	"""In-memory-style repo backed by a temp SQLite file."""
	db = DatabaseManager(db_path=str(tmp_path / "test.db"), skip_auto_seed=True)
	return DatabaseRepository(db)


# ── Portfolio CRUD ──────────────────────────────────────────────────────────


class TestCreatePortfolio:
	def test_creates_and_returns_row(self, repo):
		p = repo.create_portfolio("Alpha", "desc")
		assert p["name"] == "Alpha"
		assert p["description"] == "desc"
		assert p["id"] == 1

	def test_duplicate_name_raises(self, repo):
		repo.create_portfolio("Alpha")
		with pytest.raises(ValueError, match="already exists"):
			repo.create_portfolio("Alpha")

	def test_description_optional(self, repo):
		p = repo.create_portfolio("Beta")
		assert p["description"] is None


class TestListPortfolios:
	def test_empty_list(self, repo):
		assert repo.list_portfolios() == []

	def test_lists_all_with_tx_count(self, repo):
		repo.create_portfolio("A")
		repo.create_portfolio("B")
		result = repo.list_portfolios()
		assert len(result) == 2
		assert all(r["transaction_count"] == 0 for r in result)

	def test_ordered_by_name(self, repo):
		repo.create_portfolio("Zebra")
		repo.create_portfolio("Alpha")
		names = [p["name"] for p in repo.list_portfolios()]
		assert names == ["Alpha", "Zebra"]


class TestGetPortfolio:
	def test_returns_portfolio(self, repo):
		repo.create_portfolio("X")
		p = repo.get_portfolio(1)
		assert p is not None
		assert p["name"] == "X"

	def test_missing_returns_none(self, repo):
		assert repo.get_portfolio(999) is None


class TestDeletePortfolio:
	def test_deletes_portfolio(self, repo):
		repo.create_portfolio("Del")
		assert repo.delete_portfolio(1) == "deleted"
		assert repo.get_portfolio(1) is None

	def test_not_found(self, repo):
		assert repo.delete_portfolio(999) == "not_found"


# ── Transactions ────────────────────────────────────────────────────────────


class TestRecordTransaction:
	def test_buy_creates_holding(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(1, "AAPL", "BUY", 10, 150.0, "2024-01-01")
		holdings = repo.get_holdings(1)
		assert len(holdings) == 1
		assert holdings[0]["symbol"] == "AAPL"
		assert holdings[0]["total_shares"] == 10
		assert holdings[0]["average_cost"] == pytest.approx(150.0)

	def test_buy_fees_included_in_cost_basis(self, repo):
		repo.create_portfolio("P")
		# 10 shares @ $100 + $10 fee → avg cost = $101/share
		repo.record_transaction(1, "AAPL", "BUY", 10, 100.0, "2024-01-01", fees=10.0)
		holdings = repo.get_holdings(1)
		assert holdings[0]["average_cost"] == pytest.approx(101.0)

	def test_buy_updates_average_cost(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(1, "AAPL", "BUY", 10, 100.0, "2024-01-01")
		repo.record_transaction(1, "AAPL", "BUY", 10, 200.0, "2024-01-02")
		holdings = repo.get_holdings(1)
		assert holdings[0]["total_shares"] == 20
		assert holdings[0]["average_cost"] == pytest.approx(150.0)

	def test_buy_average_cost_with_fees_across_two_buys(self, repo):
		repo.create_portfolio("P")
		# Buy 1: 10 @ $100 + $5 fee → effective $1005
		# Buy 2: 10 @ $200 + $5 fee → effective $2005
		# avg = (1005 + 2005) / 20 = $150.50
		repo.record_transaction(1, "AAPL", "BUY", 10, 100.0, "2024-01-01", fees=5.0)
		repo.record_transaction(1, "AAPL", "BUY", 10, 200.0, "2024-01-02", fees=5.0)
		holdings = repo.get_holdings(1)
		assert holdings[0]["average_cost"] == pytest.approx(150.50)

	def test_sell_reduces_shares(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(1, "AAPL", "BUY", 20, 100.0, "2024-01-01")
		repo.record_transaction(1, "AAPL", "SELL", 5, 120.0, "2024-01-02")
		holdings = repo.get_holdings(1)
		assert holdings[0]["total_shares"] == 15

	def test_sell_all_removes_holding(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(1, "AAPL", "BUY", 10, 100.0, "2024-01-01")
		repo.record_transaction(1, "AAPL", "SELL", 10, 150.0, "2024-01-02")
		assert repo.get_holdings(1) == []

	def test_oversell_raises(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(1, "AAPL", "BUY", 5, 100.0, "2024-01-01")
		with pytest.raises(ValueError, match="Cannot sell"):
			repo.record_transaction(1, "AAPL", "SELL", 10, 110.0, "2024-01-02")

	def test_dividend_no_holding_change(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(1, "AAPL", "BUY", 10, 100.0, "2024-01-01")
		repo.record_transaction(1, "AAPL", "DIVIDEND", 1, 0.5, "2024-04-01")
		holdings = repo.get_holdings(1)
		assert holdings[0]["total_shares"] == 10

	def test_transaction_logged(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(
			1, "MSFT", "BUY", 5, 300.0, "2024-03-01", fees=1.5, notes="first buy"
		)
		txns = repo.get_transactions(1)
		assert len(txns) == 1
		assert txns[0]["symbol"] == "MSFT"
		assert txns[0]["fees"] == 1.5
		assert txns[0]["notes"] == "first buy"

	def test_multiple_symbols_independent_holdings(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(1, "AAPL", "BUY", 5, 100.0, "2024-01-01")
		repo.record_transaction(1, "GOOG", "BUY", 3, 200.0, "2024-01-02")
		holdings = repo.get_holdings(1)
		assert len(holdings) == 2


# ── Repo-layer input validation ─────────────────────────────────────────────


class TestRecordTransactionValidation:
	def test_invalid_transaction_type_raises(self, repo):
		repo.create_portfolio("P")
		with pytest.raises(ValueError, match="Invalid transaction_type"):
			repo.record_transaction(1, "AAPL", "GRANT", 5, 100.0, "2024-01-01")

	def test_zero_quantity_raises(self, repo):
		repo.create_portfolio("P")
		with pytest.raises(ValueError, match="quantity"):
			repo.record_transaction(1, "AAPL", "BUY", 0, 100.0, "2024-01-01")

	def test_negative_quantity_raises(self, repo):
		repo.create_portfolio("P")
		with pytest.raises(ValueError, match="quantity"):
			repo.record_transaction(1, "AAPL", "BUY", -1, 100.0, "2024-01-01")

	def test_zero_price_raises(self, repo):
		repo.create_portfolio("P")
		with pytest.raises(ValueError, match="price_per_share"):
			repo.record_transaction(1, "AAPL", "BUY", 5, 0.0, "2024-01-01")

	def test_negative_fees_raises(self, repo):
		repo.create_portfolio("P")
		with pytest.raises(ValueError, match="fees"):
			repo.record_transaction(1, "AAPL", "BUY", 5, 100.0, "2024-01-01", fees=-1.0)

	def test_invalid_type_does_not_mutate_holdings(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(1, "AAPL", "BUY", 10, 100.0, "2024-01-01")
		with pytest.raises(ValueError):
			repo.record_transaction(1, "AAPL", "GRANT", 5, 100.0, "2024-01-02")
		# Holdings must be unchanged
		assert repo.get_holdings(1)[0]["total_shares"] == 10


# ── Cascade delete ──────────────────────────────────────────────────────────


class TestCascadeDelete:
	def test_delete_removes_transactions_and_holdings(self, repo):
		repo.create_portfolio("P")
		repo.record_transaction(1, "AAPL", "BUY", 5, 100.0, "2024-01-01")
		repo.delete_portfolio(1)
		# Holdings and transactions should be gone (cascade)
		assert repo.get_holdings(1) == []
		assert repo.get_transactions(1) == []
