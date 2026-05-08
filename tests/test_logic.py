from unittest.mock import MagicMock, patch

import pytest

from core.analysis.indices import get_index_components
from core.analysis.preprocessing import postprocess_score, preprocess_metric_value
from core.database import DatabaseManager, DatabaseRepository
from core.profiles import get_profile_weights
from core.schema import AssetData
from core.ui.formatters import format_display_value


@pytest.fixture
def repo(tmp_path):
	db_file = tmp_path / "test_market_logic.db"
	manager = DatabaseManager(str(db_file))
	repo = DatabaseRepository(manager)

	# Seed for tests
	repo.upsert_profile("growth", "Growth")
	repo.upsert_profile_weight("growth", "revenueGrowth", 2.5)

	yield repo
	manager.close()


def test_preprocess_metric_value():
	asset = AssetData(symbol="TEST", metrics={"dividendYield": 0.05})

	# Normal case
	assert preprocess_metric_value("dividendYield", 0.05, asset) == 0.05

	# Fallback case
	assert preprocess_metric_value("yield", None, asset) == 0.05

	# Institutional cap
	assert preprocess_metric_value("heldPercentInstitutions", 1.5, asset) == 1.0

	# Invalid data
	assert preprocess_metric_value("test", "not a number", asset) is None


def test_postprocess_score():
	# Negative P/E should result in 0 score
	assert postprocess_score("trailingPE", -5.0, 0.5) == 0.0
	# Normal case should be unchanged
	assert postprocess_score("trailingPE", 15.0, 0.5) == 0.5


def test_profile_weights_loading(repo):
	weights = get_profile_weights(repo, "growth")
	assert isinstance(weights, dict)
	assert weights.get("revenueGrowth") == 2.5


def test_format_display_value():
	assert format_display_value(0.05, "percentage", True) == "5.00%"
	assert format_display_value(5.0, "percentage", False) == "5.00%"
	assert format_display_value(30.0, "multiplier") == "30.00x"
	assert format_display_value(100.5, "currency") == "$100.50"
	assert format_display_value(1.234, None) == "1.23"


def test_get_index_components():
	# Test that it returns a list of components for a known ETF
	import pandas as pd

	with patch("yfinance.Ticker") as mock_yf:
		# Mock top holdings for fallback
		mock_yf.return_value.info = {"fundFamily": "Unknown"}
		mock_holdings = MagicMock(spec=pd.DataFrame)
		mock_holdings.empty = False
		mock_holdings.index.tolist.return_value = ["AAPL", "MSFT"]

		mock_funds = MagicMock()
		mock_funds.top_holdings = mock_holdings
		mock_yf.return_value.funds_data = mock_funds

		components = get_index_components("SPY")
		assert isinstance(components, list)
		assert len(components) > 1
		assert "AAPL" in components
