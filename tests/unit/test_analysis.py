import pytest

from core.evaluation import evaluate_metric
from core.schema import AssetData, AssetType

# Import from the new modular structure
from core.scorers import (
	calculate_bell_score,
	calculate_linear_score,
	calculate_sigmoid_score,
	calculate_threshold_score,
)


def test_sigmoid_math():
	assert calculate_sigmoid_score(10, 10, 30) == pytest.approx(0.95, abs=0.01)
	assert calculate_sigmoid_score(20, 10, 30) == pytest.approx(0.50, abs=0.01)


def test_linear_math():
	# Higher is better: best=20, worst=10 → 15 should be 50%
	assert calculate_linear_score(15, 20, 10) == pytest.approx(0.5)

	# Lower is better: best=10, worst=20 → 15 should be 50%
	assert calculate_linear_score(15, 10, 20) == pytest.approx(0.5)

	# Clamping
	assert calculate_linear_score(25, 20, 10) == 1.0
	assert calculate_linear_score(5, 20, 10) == -0.5


def test_bell_curve_math():
	assert calculate_bell_score(50, 50, 10) == 1.0
	assert calculate_bell_score(60, 50, 10) < 1.0
	assert calculate_bell_score(40, 50, 10) < 1.0


def test_threshold_math():
	assert calculate_threshold_score(0.025, 0.02) == 1.0
	assert calculate_threshold_score(0.015, 0.02) == 0.0


def test_evaluate_metric_dispatch():
	# Test Bell Curve
	benchmark = {
		"name": "Debt",
		"metric": "d2e",
		"type": "bell_curve",
		"target": 50,
		"width": 10,
	}
	asset = AssetData(symbol="TEST", asset_type=AssetType.STOCK, metrics={"d2e": 50})
	# Provide dummy profile weights for the test
	dummy_weights = {"d2e": 1.0}
	res = evaluate_metric(asset, benchmark, dummy_weights)
	assert res["pct"] == 1.0

	# Test Threshold
	benchmark = {
		"name": "Div",
		"metric": "yield",
		"type": "threshold",
		"threshold": 0.02,
	}
	asset = AssetData(
		symbol="TEST", asset_type=AssetType.STOCK, metrics={"yield": 0.03}
	)
	# Provide dummy profile weights for the test
	dummy_weights = {"yield": 1.0}
	res = evaluate_metric(asset, benchmark, dummy_weights)
	assert res["pct"] == 1.0


def test_short_interest_scoring():
	# Test high short interest (should be low strength)
	benchmark = {
		"name": "Short %",
		"metric": "shortPercentOfFloat",
		"type": "sigmoid",
		"best": 0.02,
		"worst": 0.15,
	}
	# 15% short interest should be near 'worst' (close to 0 strength)
	asset = AssetData(
		symbol="TEST", asset_type=AssetType.STOCK, metrics={"shortPercentOfFloat": 0.15}
	)
	res = evaluate_metric(asset, benchmark, {"shortPercentOfFloat": 1.0})
	assert res["pct"] < 0.1  # Very low strength

	# Test low short interest (should be high strength)
	asset = AssetData(
		symbol="TEST", asset_type=AssetType.STOCK, metrics={"shortPercentOfFloat": 0.02}
	)
	res = evaluate_metric(asset, benchmark, {"shortPercentOfFloat": 1.0})
	assert res["pct"] > 0.9  # Very high strength


def test_evaluate_metric_with_penalty():
	asset = AssetData(
		symbol="TEST", asset_type=AssetType.STOCK, metrics={"leverage": 5.0, "roe": 0.2}
	)

	# Reward metric
	bench_roe = {
		"metric": "roe",
		"name": "ROE",
		"type": "linear",
		"best": 0.2,
		"worst": 0.0,
		"weight": 10.0,
		"is_penalty": False,
	}

	# Penalty metric
	bench_leverage = {
		"metric": "leverage",
		"name": "Leverage Penalty",
		"type": "penalty_threshold",
		"threshold": 3.0,
		"worst": 7.0,
		"weight": 10.0,
		"is_penalty": True,
	}

	profile_config = {}  # No overrides

	# ROE score should be 10.0 (weight 10 * pct 1.0)
	res_roe = evaluate_metric(asset, bench_roe, profile_config)
	assert res_roe["pct"] == 1.0
	assert res_roe["score"] == 10.0
	assert res_roe["is_penalty"] is False

	# Leverage score should be -5.0 (weight 10 * pct -0.5)
	# (5.0 - 3.0) / (7.0 - 3.0) = 2.0 / 4.0 = 0.5 -> penalty -0.5
	res_leverage = evaluate_metric(asset, bench_leverage, profile_config)
	assert res_leverage["pct"] == -0.5
	assert res_leverage["score"] == -5.0
	assert res_leverage["is_penalty"] is True
	assert res_leverage["status"] == "-50%"


def test_evaluate_metric_penalty_override():
	asset = AssetData(
		symbol="TEST", asset_type=AssetType.STOCK, metrics={"leverage": 5.0}
	)

	bench = {
		"metric": "leverage",
		"name": "Leverage",
		"type": "linear",
		"best": 0.0,
		"worst": 10.0,
		"weight": 10.0,
		"is_penalty": False,  # Default not penalty
	}

	# Profile overrides it to be a penalty
	profile_config = {
		"leverage": {
			"weight": 10.0,
			"formula": "penalty_threshold",
			"best": 3.0,  # maps to threshold
			"worst": 7.0,
			"is_penalty": True,
		}
	}

	res = evaluate_metric(asset, bench, profile_config)
	assert res["is_penalty"] is True
	assert res["pct"] == -0.5
	assert res["score"] == -5.0
