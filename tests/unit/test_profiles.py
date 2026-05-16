"""
Tests that investor profiles produce genuinely differentiated scores.

These tests cover the full pipeline from seeded profile_metric_settings
through get_profile_weights / get_profile_config and evaluate_metric to
final weighted scores.

Historically broken (#64): profile_metric_settings was empty so all profiles
fell back to the same benchmark defaults.

Fixed by #148: profile-level formula/range overrides are now applied by
evaluate_metric, so changing a profile's 'best' value actually shifts the
metric strength percentage for the same raw asset data.
"""

import pytest

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository
from core.evaluation import evaluate_metric
from core.profiles import get_profile_config, get_profile_weights
from core.schema import AssetData, AssetType


@pytest.fixture
def seeded_repo(tmp_path):
	"""Fresh DB with full auto-seed — gives us real balanced/growth/dividend weights."""
	manager = DatabaseManager(str(tmp_path / "test.db"))
	repo = DatabaseRepository(manager)
	yield repo
	manager.close()


def test_seeded_profiles_all_load(seeded_repo):
	"""All three investor profiles must return non-empty weight dicts."""
	for profile in ("balanced", "growth", "dividend"):
		weights = get_profile_weights(seeded_repo, profile)
		assert weights, f"Profile '{profile}' returned empty weights — seed missing?"


def test_growth_upweights_revenue_growth(seeded_repo):
	"""Growth profile must weight revenue_growth higher than dividend profile does."""
	growth_w = get_profile_weights(seeded_repo, "growth")
	dividend_w = get_profile_weights(seeded_repo, "dividend")
	assert growth_w.get("revenue_growth", 0) > dividend_w.get("revenue_growth", 0)


def test_dividend_upweights_dividend_yield(seeded_repo):
	"""Dividend profile must weight dividend_yield higher than growth profile does."""
	growth_w = get_profile_weights(seeded_repo, "growth")
	dividend_w = get_profile_weights(seeded_repo, "dividend")
	assert dividend_w.get("dividend_yield", 0) > growth_w.get("dividend_yield", 0)


def test_profiles_score_same_asset_differently(seeded_repo):
	"""
	A high-growth / no-dividend asset must score higher under 'growth'
	than under 'dividend', and vice versa for a high-yield / low-growth asset.
	"""
	growth_w = get_profile_weights(seeded_repo, "growth")
	dividend_w = get_profile_weights(seeded_repo, "dividend")

	# Benchmarks for the two metrics we care about
	rev_growth_benchmark = {
		"metric": "revenue_growth",
		"name": "Revenue Growth",
		"type": "sigmoid",
		"best": 0.25,
		"worst": 0.0,
		"weight": 1.0,
	}
	div_yield_benchmark = {
		"metric": "dividend_yield",
		"name": "Dividend Yield",
		"type": "sigmoid",
		"best": 0.04,
		"worst": 0.0,
		"weight": 1.0,
	}

	# Asset A: strong revenue growth, no dividend (typical growth stock)
	growth_stock = AssetData(
		symbol="GROWTH",
		asset_type=AssetType.STOCK,
		metrics={"revenue_growth": 0.30, "dividend_yield": 0.0},
	)

	# Asset B: high dividend yield, flat revenue (typical income stock)
	income_stock = AssetData(
		symbol="INCOME",
		asset_type=AssetType.STOCK,
		metrics={"revenue_growth": 0.02, "dividend_yield": 0.05},
	)

	def total_score(asset, weights):
		results = [
			evaluate_metric(asset, rev_growth_benchmark, weights),
			evaluate_metric(asset, div_yield_benchmark, weights),
		]
		total_w = sum(r["weight"] for r in results)
		return sum(r["score"] for r in results) / total_w if total_w else 0.0

	growth_stock_under_growth = total_score(growth_stock, growth_w)
	growth_stock_under_dividend = total_score(growth_stock, dividend_w)
	income_stock_under_growth = total_score(income_stock, growth_w)
	income_stock_under_dividend = total_score(income_stock, dividend_w)

	assert growth_stock_under_growth > growth_stock_under_dividend, (
		"Growth stock should score higher under growth profile than dividend profile"
	)
	assert income_stock_under_dividend > income_stock_under_growth, (
		"Income stock should score higher under dividend profile than growth profile"
	)


def test_profile_fallback_uses_balanced(seeded_repo):
	"""Unknown profile name must fall back to balanced weights, not return empty."""
	weights = get_profile_weights(seeded_repo, "nonexistent_profile")
	balanced = get_profile_weights(seeded_repo, "balanced")
	assert weights == balanced


# ── get_profile_config tests (issue #148) ─────────────────────────────────────


def test_get_profile_config_returns_full_settings(seeded_repo):
	"""get_profile_config must include weight, best, worst, formula per metric."""
	config = get_profile_config(seeded_repo, "balanced")
	assert config, "Config must be non-empty for seeded balanced profile"
	for key, setting in config.items():
		assert "weight" in setting, f"{key}: missing 'weight'"
		assert "best" in setting, f"{key}: missing 'best'"
		assert "worst" in setting, f"{key}: missing 'worst'"
		assert "formula" in setting, f"{key}: missing 'formula'"


def test_profile_curve_override_shifts_strength():
	"""Real non-NULL curve override must shift the metric strength %."""
	benchmark = {
		"metric": "pe_ratio",
		"name": "P/E Ratio",
		"type": "sigmoid",
		"best": 15.0,
		"worst": 50.0,
		"weight": 1.0,
	}
	asset = AssetData(
		symbol="TEST",
		asset_type=AssetType.STOCK,
		metrics={"pe_ratio": 25.0},
	)

	# NULL range → benchmark curve used (best=15, worse for P/E=25)
	null_override = {
		"pe_ratio": {"weight": 1.0, "best": None, "worst": None, "formula": None}
	}
	# Real override → best=25 means P/E=25 is now ideal → much higher score
	real_override = {
		"pe_ratio": {"weight": 1.0, "best": 25.0, "worst": 50.0, "formula": "sigmoid"}
	}

	null_result = evaluate_metric(asset, benchmark, null_override)
	real_result = evaluate_metric(asset, benchmark, real_override)

	msg = f"Real override (best=25) should score P/E=25 higher than null (benchmark best=15). Got null={null_result['pct']:.3f}, real={real_result['pct']:.3f}"
	assert real_result["pct"] > null_result["pct"], msg


def test_null_range_falls_back_to_benchmark_params():
	"""NULL range_min/range_max must use the benchmark curve, not default (0, 100)."""
	benchmark = {
		"metric": "pe_ratio",
		"name": "P/E Ratio",
		"type": "sigmoid",
		"best": 15.0,
		"worst": 50.0,
		"weight": 1.0,
	}
	asset = AssetData(
		symbol="TEST",
		asset_type=AssetType.STOCK,
		metrics={"pe_ratio": 25.0},
	)

	null_config = {
		"pe_ratio": {"weight": 1.0, "best": None, "worst": None, "formula": None}
	}
	no_profile = {}

	null_result = evaluate_metric(asset, benchmark, null_config)
	no_profile_result = evaluate_metric(asset, benchmark, no_profile)

	# Both should score identically — NULL override == no override == benchmark params
	assert abs(null_result["pct"] - no_profile_result["pct"]) < 1e-9, (
		f"NULL profile range must yield same score as benchmark default. Got {null_result['pct']:.4f} vs {no_profile_result['pct']:.4f}"
	)
	# And must NOT be near 1.0 (which would indicate the broken 0/100 override)
	assert null_result["pct"] < 0.95, (
		"Score suspiciously high — likely using wrong best=0 worst=100 override"
	)


def test_profile_formula_override_independent_of_range():
	"""Formula override must apply even when range_min/range_max are NULL."""
	benchmark = {
		"metric": "revenue_growth",
		"name": "Revenue Growth",
		"type": "sigmoid",
		"best": 0.25,
		"worst": 0.0,
		"weight": 1.0,
	}
	asset = AssetData(
		symbol="TEST",
		asset_type=AssetType.STOCK,
		metrics={"revenue_growth": 0.15},
	)

	# NULL range but explicit formula override — should still apply the formula
	formula_only = {
		"revenue_growth": {
			"weight": 1.0,
			"best": None,
			"worst": None,
			"formula": "linear",
		}
	}
	no_override = {
		"revenue_growth": {"weight": 1.0, "best": None, "worst": None, "formula": None}
	}

	formula_result = evaluate_metric(asset, benchmark, formula_only)
	no_formula_result = evaluate_metric(asset, benchmark, no_override)

	assert formula_result["pct"] != no_formula_result["pct"], (
		"Formula-only override (linear vs sigmoid) must produce a different score even with NULL ranges"
	)


def test_legacy_weight_dict_still_works():
	"""evaluate_metric must accept the old Dict[str, float] weight format."""
	benchmark = {
		"metric": "pe_ratio",
		"name": "P/E Ratio",
		"type": "sigmoid",
		"best": 15.0,
		"worst": 50.0,
		"weight": 1.0,
	}
	asset = AssetData(
		symbol="TEST",
		asset_type=AssetType.STOCK,
		metrics={"pe_ratio": 20.0},
	)

	legacy_weights = {"pe_ratio": 2.0}
	result = evaluate_metric(asset, benchmark, legacy_weights)
	assert result["weight"] == 2.0
	assert result["pct"] > 0
