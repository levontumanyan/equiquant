from unittest.mock import MagicMock, patch

from core.evaluation import evaluate_metric
from core.orchestrator import analyze_asset
from core.schema import AssetData, AssetType
from core.scorers import calculate_flat_penalty_score, calculate_penalty_threshold_score


def test_penalty_threshold_score():
	# Penalty starts at 3.0, reaches max at 10.0 (e.g. Debt/Equity)
	threshold, worst = 3.0, 10.0

	# Below threshold -> no penalty
	assert calculate_penalty_threshold_score(1.0, threshold, worst) == 0.0
	assert calculate_penalty_threshold_score(3.0, threshold, worst) == 0.0

	# At worst -> -1.0
	assert calculate_penalty_threshold_score(10.0, threshold, worst) == -1.0

	# Beyond worst -> -1.0
	assert calculate_penalty_threshold_score(15.0, threshold, worst) == -1.0

	# Midpoint -> -0.5
	# (6.5 - 3.0) / (10.0 - 3.0) = 3.5 / 7.0 = 0.5
	assert calculate_penalty_threshold_score(6.5, threshold, worst) == -0.5


def test_penalty_threshold_inverted():
	# Penalty starts at 1.0 and gets worse as it goes DOWN (e.g. Current Ratio < 1.0)
	threshold, worst = 1.0, 0.5

	# Above threshold -> no penalty
	assert calculate_penalty_threshold_score(1.5, threshold, worst) == 0.0
	assert calculate_penalty_threshold_score(1.0, threshold, worst) == 0.0

	# At worst -> -1.0
	assert calculate_penalty_threshold_score(0.5, threshold, worst) == -1.0

	# Below worst -> -1.0
	assert calculate_penalty_threshold_score(0.1, threshold, worst) == -1.0

	# Midpoint -> -0.5
	assert calculate_penalty_threshold_score(0.75, threshold, worst) == -0.5


def test_flat_penalty_score():
	threshold = 5.0
	penalty = -0.3

	assert calculate_flat_penalty_score(3.0, threshold, penalty) == 0.0
	assert calculate_flat_penalty_score(5.0, threshold, penalty) == penalty
	assert calculate_flat_penalty_score(10.0, threshold, penalty) == penalty


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


def test_analyze_asset_total_score_with_penalties():
	asset = AssetData(
		symbol="TEST", asset_type=AssetType.STOCK, metrics={"m1": 10, "m2": 10}
	)

	# Mock evaluate_metric to return one reward and one penalty
	results = [
		{
			"metric": "m1",
			"name": "Reward",
			"score": 10.0,
			"weight": 10.0,
			"pct": 1.0,
			"is_penalty": False,
		},
		{
			"metric": "m2",
			"name": "Penalty",
			"score": -5.0,
			"weight": 10.0,
			"pct": -0.5,
			"is_penalty": True,
		},
	]

	benchmark_defs = [
		{"metric": "m1", "weight": 10.0},
		{"metric": "m2", "weight": 10.0},
	]

	repo = MagicMock()
	repo.get_global_benchmarks.return_value = benchmark_defs

	with patch("core.orchestrator.evaluate_metric") as mock_eval:
		mock_eval.side_effect = results

		res = analyze_asset(asset, profile="balanced", repo=repo)

		# total_score = 10.0 - 5.0 = 5.0
		# max_score = weight of m1 only = 10.0
		# final_pct = 5.0 / 10.0 * 100 = 50.0%
		assert res["score"] == 50.0
		assert len(res["results"]) == 2
		assert res["results"][0]["score"] == 10.0
		assert res["results"][1]["score"] == -5.0


def test_analyze_asset_total_score_no_penalty_impact():
	asset = AssetData(
		symbol="TEST", asset_type=AssetType.STOCK, metrics={"m1": 10, "m2": 0}
	)

	results = [
		{
			"metric": "m1",
			"name": "Reward",
			"score": 10.0,
			"weight": 10.0,
			"pct": 1.0,
			"is_penalty": False,
		},
		{
			"metric": "m2",
			"name": "Penalty",
			"score": 0.0,
			"weight": 10.0,
			"pct": 0.0,
			"is_penalty": True,
		},
	]

	benchmark_defs = [
		{"metric": "m1", "weight": 10.0},
		{"metric": "m2", "weight": 10.0},
	]

	repo = MagicMock()
	repo.get_global_benchmarks.return_value = benchmark_defs

	with patch("core.orchestrator.evaluate_metric") as mock_eval:
		mock_eval.side_effect = results

		res = analyze_asset(asset, profile="balanced", repo=repo)

		# total_score = 10.0 + 0.0 = 10.0
		# max_score = 10.0
		# final_pct = 100.0%
		assert res["score"] == 100.0
