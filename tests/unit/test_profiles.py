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
	"""
	Changing a profile's 'best' value must shift the metric strength %.
	This is the core regression fixed by #148 — previously evaluate_metric
	ignored profile-level range overrides entirely.
	"""
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

	# Default profile config — uses benchmark curve (best=15)
	default_config = {
		"pe_ratio": {"weight": 1.0, "best": 15.0, "worst": 50.0, "formula": "sigmoid"}
	}

	# Custom profile — user moved 'best' to 25, meaning 25x P/E is now ideal
	# Sigmoid should now score 25.0 much higher than with best=15
	custom_config = {
		"pe_ratio": {"weight": 1.0, "best": 25.0, "worst": 50.0, "formula": "sigmoid"}
	}

	default_result = evaluate_metric(asset, benchmark, default_config)
	custom_result = evaluate_metric(asset, benchmark, custom_config)

	msg = f"Custom profile (best=25) should score P/E=25 higher than default (best=15). Got default={default_result['pct']:.3f}, custom={custom_result['pct']:.3f}"
	assert custom_result["pct"] > default_result["pct"], msg


def test_profile_formula_override_changes_scorer():
	"""
	Switching formula from sigmoid to linear in a profile must change the score.
	"""
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

	sigmoid_config = {
		"revenue_growth": {
			"weight": 1.0,
			"best": 0.25,
			"worst": 0.0,
			"formula": "sigmoid",
		}
	}
	linear_config = {
		"revenue_growth": {
			"weight": 1.0,
			"best": 0.25,
			"worst": 0.0,
			"formula": "linear",
		}
	}

	sigmoid_result = evaluate_metric(asset, benchmark, sigmoid_config)
	linear_result = evaluate_metric(asset, benchmark, linear_config)

	assert sigmoid_result["pct"] != linear_result["pct"], (
		"sigmoid and linear scorers must produce different results for the same input"
	)


def test_legacy_weight_dict_still_works():
	"""
	evaluate_metric must accept the old Dict[str, float] weight format so
	existing callers are not broken by the #148 refactor.
	"""
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
