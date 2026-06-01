from unittest.mock import MagicMock, patch

import pytest

from core.analysis.indices import get_index_components
from core.analysis.preprocessing import postprocess_score, preprocess_metric_value
from core.database import DatabaseManager, DatabaseRepository
from core.metrics import FORWARD_PE, INSTITUTION_OWNERSHIP, PE_RATIO, TRAILING_PE
from core.profiles import get_profile_weights
from core.schema import AssetData
from core.utils.formatters import format_display_value


@pytest.fixture
def repo(tmp_path):
	db_file = tmp_path / "test_market_logic.db"
	manager = DatabaseManager(str(db_file))

	repo = DatabaseRepository(manager)

	# Seed for tests
	repo.upsert_profile("growth", "Growth")
	repo.upsert_profile_setting("growth", "revenueGrowth", 2.5, 0.0, 100.0, "sigmoid")
	yield repo
	manager.close()


def test_preprocess_metric_value():
	asset = AssetData(symbol="TEST", metrics={})

	# Normal numeric value passes through
	assert preprocess_metric_value("pe_ratio", 15.0, asset) == 15.0

	# Institution ownership capped at 1.0
	assert preprocess_metric_value(INSTITUTION_OWNERSHIP, 1.5, asset) == 1.0
	assert preprocess_metric_value(INSTITUTION_OWNERSHIP, 0.85, asset) == 0.85

	# Invalid data returns None
	assert preprocess_metric_value("test", "not a number", asset) is None
	assert preprocess_metric_value("test", None, asset) is None

	# NaN handling (fix for #164)
	assert preprocess_metric_value("test", float("nan"), asset) is None


def test_postprocess_score_pe_family():
	# Negative P/E — all three P/E family members — must return 0
	assert postprocess_score(PE_RATIO, -5.0, 0.5) == 0.0
	assert postprocess_score(FORWARD_PE, -86.14, 1.0) == 0.0
	assert postprocess_score(TRAILING_PE, -12.0, 0.9) == 0.0

	# Positive P/E passes through unchanged
	assert postprocess_score(PE_RATIO, 15.0, 0.5) == 0.5
	assert postprocess_score(FORWARD_PE, 20.0, 0.7) == 0.7

	# Non-PE metrics are unaffected even when negative
	assert postprocess_score("revenue_growth", -0.05, 0.1) == 0.1


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
