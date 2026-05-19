"""
Tests for data-driven sector-relative and batch-relative scoring.

The old sector_benchmarks (static overrides) are deprecated. These tests cover
the new compute_relative_benchmarks algorithm and its integration with the
orchestrator's context routing.
"""

import pytest

from core.analysis.relative import (
	_percentile,
	compute_batch_relative_benchmarks,
	compute_relative_benchmarks,
	extract_metric_values,
)
from core.schema import AssetData, AssetType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_asset(
	symbol: str,
	pe: float | None = None,
	roe: float | None = None,
	debt_to_equity: float | None = None,
) -> AssetData:
	"""Build a minimal AssetData for testing."""
	raw: dict = {}
	if pe is not None:
		raw["trailingPE"] = pe
	if roe is not None:
		raw["returnOnEquity"] = roe
	if debt_to_equity is not None:
		raw["debtToEquity"] = debt_to_equity
	return AssetData(
		symbol=symbol,
		asset_type=AssetType.STOCK,
		name=symbol,
		sector="Technology",
		industry="Software",
		metrics=raw,
		raw_data=raw,
	)


def _make_benchmark(
	metric: str,
	formula: str = "sigmoid",
	best: float = 15.0,
	worst: float = 50.0,
	target: float | None = None,
	width: float | None = None,
	target_min: float | None = None,
	target_max: float | None = None,
	threshold: float | None = None,
) -> dict:
	b: dict = {
		"metric": metric,
		"type": formula,
		"best": best,
		"worst": worst,
		"weight": 1.0,
	}
	if target is not None:
		b["target"] = target
	if width is not None:
		b["width"] = width
	if target_min is not None:
		b["target_min"] = target_min
	if target_max is not None:
		b["target_max"] = target_max
	if threshold is not None:
		b["threshold"] = threshold
	return b


# ---------------------------------------------------------------------------
# _percentile
# ---------------------------------------------------------------------------


class TestPercentile:
	def test_single_value_returns_that_value(self):
		assert _percentile([42.0], 50) == 42.0

	def test_two_values_median(self):
		result = _percentile([10.0, 20.0], 50)
		assert result == pytest.approx(15.0)

	def test_p0_returns_min(self):
		values = [1.0, 2.0, 3.0, 4.0, 5.0]
		assert _percentile(values, 0) == pytest.approx(1.0)

	def test_p100_returns_max(self):
		values = [1.0, 2.0, 3.0, 4.0, 5.0]
		assert _percentile(values, 100) == pytest.approx(5.0)

	def test_p25_p75_on_symmetric_list(self):
		values = sorted([10.0, 20.0, 30.0, 40.0, 50.0])
		p25 = _percentile(values, 25)
		p75 = _percentile(values, 75)
		assert p25 == pytest.approx(20.0)
		assert p75 == pytest.approx(40.0)

	def test_interpolation_between_indices(self):
		values = [0.0, 10.0, 20.0, 30.0]
		# P50 should interpolate between index 1 (10.0) and index 2 (20.0)
		result = _percentile(values, 50)
		assert result == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# extract_metric_values
# ---------------------------------------------------------------------------


class TestExtractMetricValues:
	def test_extracts_present_values(self):
		assets = [
			_make_asset("A", pe=10.0),
			_make_asset("B", pe=20.0),
			_make_asset("C", pe=30.0),
		]
		result = extract_metric_values(assets, ["trailingPE"])
		assert result["trailingPE"] == pytest.approx([10.0, 20.0, 30.0])

	def test_skips_none_values(self):
		assets = [
			_make_asset("A", pe=10.0),
			_make_asset("B", pe=None),
			_make_asset("C", pe=30.0),
		]
		result = extract_metric_values(assets, ["trailingPE"])
		assert len(result["trailingPE"]) == 2
		assert 10.0 in result["trailingPE"]
		assert 30.0 in result["trailingPE"]

	def test_missing_metric_returns_empty_list(self):
		assets = [_make_asset("A", pe=10.0)]
		result = extract_metric_values(assets, ["nonexistent_metric"])
		assert result["nonexistent_metric"] == []

	def test_multiple_metrics(self):
		assets = [
			_make_asset("A", pe=10.0, roe=0.15),
			_make_asset("B", pe=20.0, roe=0.25),
		]
		result = extract_metric_values(assets, ["trailingPE", "returnOnEquity"])
		assert len(result["trailingPE"]) == 2
		assert len(result["returnOnEquity"]) == 2


# ---------------------------------------------------------------------------
# compute_relative_benchmarks — sigmoid / linear formulas
# ---------------------------------------------------------------------------


class TestComputeRelativeBenchmarksSigmoid:
	def _run(self, peer_pes, global_best=15.0, global_worst=50.0):
		bench = [
			_make_benchmark("pe_ratio", "sigmoid", best=global_best, worst=global_worst)
		]
		values = {"pe_ratio": peer_pes}
		return compute_relative_benchmarks(bench, values, min_peers=3)

	def test_higher_is_better_uses_p75_as_best(self):
		# Global: best=15 (low PE = better), worst=50
		# Actually best < worst means lower is better for PE
		# Let's test with a metric where higher is better: ROE
		bench = [_make_benchmark("roe", "sigmoid", best=0.20, worst=0.05)]
		values = {"roe": [0.05, 0.10, 0.15, 0.20, 0.25]}
		result = compute_relative_benchmarks(bench, values, min_peers=3)
		b = result[0]
		# higher is better: best > worst (0.20 > 0.05) → best=P75, worst=P25
		assert b["best"] > b["worst"]
		assert b["best"] == pytest.approx(
			_percentile(sorted([0.05, 0.10, 0.15, 0.20, 0.25]), 75)
		)
		assert b["worst"] == pytest.approx(
			_percentile(sorted([0.05, 0.10, 0.15, 0.20, 0.25]), 25)
		)

	def test_lower_is_better_uses_p25_as_best(self):
		# PE ratio: lower is better → global best=15 < global worst=50
		bench = [_make_benchmark("pe_ratio", "sigmoid", best=15.0, worst=50.0)]
		peer_pes = sorted([10.0, 15.0, 20.0, 30.0, 40.0])
		values = {"pe_ratio": peer_pes}
		result = compute_relative_benchmarks(bench, values, min_peers=3)
		b = result[0]
		# lower is better → best=P25 (lower), worst=P75 (higher)
		assert b["best"] < b["worst"]
		assert b["best"] == pytest.approx(_percentile(peer_pes, 25))
		assert b["worst"] == pytest.approx(_percentile(peer_pes, 75))

	def test_falls_back_to_global_when_too_few_peers(self):
		result = self._run([10.0, 20.0], global_best=15.0, global_worst=50.0)
		assert result[0]["best"] == pytest.approx(15.0)
		assert result[0]["worst"] == pytest.approx(50.0)

	def test_exactly_min_peers_engages_relative_logic(self):
		# Use values where P25 clearly differs from the global best of 15.0
		# [30, 40, 50] → P25 = 35.0, not 15.0
		result = self._run([30.0, 40.0, 50.0], global_best=15.0, global_worst=50.0)
		# 3 peers = min_peers=3 → relative logic engages
		# lower is better (best=15 < worst=50) → best=P25=35.0
		assert result[0]["best"] == pytest.approx(
			_percentile(sorted([30.0, 40.0, 50.0]), 25)
		)

	def test_linear_formula_same_direction_logic(self):
		bench = [_make_benchmark("revenue_growth", "linear", best=0.15, worst=-0.05)]
		values = {"revenue_growth": [-0.05, 0.0, 0.05, 0.10, 0.20]}
		result = compute_relative_benchmarks(bench, values, min_peers=3)
		b = result[0]
		# higher is better (0.15 > -0.05) → best=P75
		assert b["best"] > b["worst"]

	def test_metric_not_in_values_uses_global(self):
		bench = [_make_benchmark("pe_ratio", "sigmoid", best=15.0, worst=50.0)]
		result = compute_relative_benchmarks(bench, {}, min_peers=3)
		assert result[0]["best"] == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# compute_relative_benchmarks — bell_curve formula
# ---------------------------------------------------------------------------


class TestComputeRelativeBenchmarksBellCurve:
	def test_target_is_median(self):
		bench = [_make_benchmark("peg", "bell_curve", target=1.0, width=0.5)]
		bench[0].pop("best", None)
		bench[0].pop("worst", None)
		values = {"peg": [0.5, 1.0, 1.5, 2.0, 2.5]}
		result = compute_relative_benchmarks(bench, values, min_peers=3)
		import statistics

		expected_target = statistics.median([0.5, 1.0, 1.5, 2.0, 2.5])
		assert result[0]["target"] == pytest.approx(expected_target)

	def test_width_is_iqr_half(self):
		bench = [_make_benchmark("peg", "bell_curve", target=1.0, width=0.5)]
		bench[0].pop("best", None)
		bench[0].pop("worst", None)
		values = {"peg": [1.0, 2.0, 3.0, 4.0, 5.0]}
		result = compute_relative_benchmarks(bench, values, min_peers=3)
		sorted_vals = [1.0, 2.0, 3.0, 4.0, 5.0]
		q75 = _percentile(sorted_vals, 75)
		q25 = _percentile(sorted_vals, 25)
		expected_width = (q75 - q25) / 2.0
		assert result[0]["width"] == pytest.approx(expected_width)

	def test_width_clamped_above_zero_for_identical_values(self):
		bench = [_make_benchmark("peg", "bell_curve", target=1.0, width=0.5)]
		bench[0].pop("best", None)
		bench[0].pop("worst", None)
		values = {"peg": [2.0, 2.0, 2.0, 2.0, 2.0]}
		result = compute_relative_benchmarks(bench, values, min_peers=3)
		assert result[0]["width"] > 0


# ---------------------------------------------------------------------------
# compute_relative_benchmarks — plateau formula
# ---------------------------------------------------------------------------


class TestComputeRelativeBenchmarksPlateau:
	def test_target_min_max_are_p33_p67(self):
		bench = [
			_make_benchmark("current_ratio", "plateau", target_min=1.5, target_max=2.5)
		]
		bench[0].pop("best", None)
		bench[0].pop("worst", None)
		vals = sorted([1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
		values = {"current_ratio": vals}
		result = compute_relative_benchmarks(bench, values, min_peers=3)
		assert result[0]["target_min"] == pytest.approx(_percentile(vals, 33))
		assert result[0]["target_max"] == pytest.approx(_percentile(vals, 67))


# ---------------------------------------------------------------------------
# compute_relative_benchmarks — threshold formula (must stay global)
# ---------------------------------------------------------------------------


class TestComputeRelativeBenchmarksThreshold:
	def test_threshold_metric_not_changed(self):
		bench = [
			{
				"metric": "positive_eps",
				"type": "threshold",
				"threshold": 0.0,
				"weight": 1.0,
			}
		]
		values = {"positive_eps": [0.5, 1.0, 1.5, 2.0, 2.5]}
		result = compute_relative_benchmarks(bench, values, min_peers=3)
		assert result[0]["threshold"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_batch_relative_benchmarks integration
# ---------------------------------------------------------------------------


class TestComputeBatchRelativeBenchmarks:
	def _make_global_benchmarks(self):
		return [
			_make_benchmark("trailingPE", "sigmoid", best=15.0, worst=50.0),
			_make_benchmark("returnOnEquity", "sigmoid", best=0.20, worst=0.05),
		]

	def test_batch_uses_asset_metric_values(self):
		assets = [
			_make_asset("A", pe=10.0, roe=0.10),
			_make_asset("B", pe=20.0, roe=0.20),
			_make_asset("C", pe=30.0, roe=0.30),
			_make_asset("D", pe=40.0, roe=0.40),
		]
		benchmarks = compute_batch_relative_benchmarks(
			assets, self._make_global_benchmarks()
		)
		pe_bench = next(b for b in benchmarks if b["metric"] == "trailingPE")
		# PE: lower is better, so best=P25, worst=P75
		peer_pes = sorted([10.0, 20.0, 30.0, 40.0])
		assert pe_bench["best"] == pytest.approx(_percentile(peer_pes, 25))
		assert pe_bench["worst"] == pytest.approx(_percentile(peer_pes, 75))

	def test_returns_global_when_too_few_assets(self):
		assets = [_make_asset("A", pe=10.0), _make_asset("B", pe=20.0)]
		benchmarks = compute_batch_relative_benchmarks(
			assets, self._make_global_benchmarks(), min_peers=3
		)
		pe_bench = next(b for b in benchmarks if b["metric"] == "trailingPE")
		assert pe_bench["best"] == pytest.approx(15.0)
		assert pe_bench["worst"] == pytest.approx(50.0)

	def test_batch_scoring_produces_relative_ranking(self):
		"""The best stock in the batch on a metric should score near 100%."""
		from core.scorers import SCORERS

		assets = [
			_make_asset("LOW_PE", pe=10.0),
			_make_asset("MID_PE", pe=25.0),
			_make_asset("HIGH_PE", pe=40.0),
			_make_asset("VHIGH_PE", pe=60.0),
		]
		global_bench = [_make_benchmark("trailingPE", "sigmoid", best=15.0, worst=50.0)]
		batch_bench = compute_batch_relative_benchmarks(assets, global_bench)
		pe_bench = next(b for b in batch_bench if b["metric"] == "trailingPE")

		scorer = SCORERS["sigmoid"]
		# The lowest PE in the batch should get the best score under relative benchmarks
		score_low = scorer(10.0, pe_bench["best"], pe_bench["worst"])
		score_high = scorer(60.0, pe_bench["best"], pe_bench["worst"])
		assert score_low > score_high, (
			"Lower PE should score higher under lower-is-better sigmoid"
		)

	def test_scores_differ_between_global_and_batch_context(self):
		"""Relative scores must differ from global scores when the batch distribution differs."""
		from core.scorers import SCORERS

		assets = [
			_make_asset("A", pe=100.0),
			_make_asset("B", pe=120.0),
			_make_asset("C", pe=140.0),
			_make_asset("D", pe=160.0),
		]
		global_bench = [_make_benchmark("trailingPE", "sigmoid", best=15.0, worst=50.0)]
		batch_bench = compute_batch_relative_benchmarks(assets, global_bench)

		scorer = SCORERS["sigmoid"]
		# Asset B under global: PE=120 far above worst=50 → very low score
		global_score = scorer(120.0, 15.0, 50.0)
		# Asset B under batch: PE=120 is in the middle of 100-160 range → higher relative score
		pe_bench = next(b for b in batch_bench if b["metric"] == "trailingPE")
		batch_score = scorer(120.0, pe_bench["best"], pe_bench["worst"])
		assert batch_score > global_score
