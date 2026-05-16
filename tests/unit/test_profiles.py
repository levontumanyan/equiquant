"""
Tests that investor profiles produce genuinely differentiated scores.

These tests cover the full pipeline from seeded profile_metric_settings
through get_profile_weights and evaluate_metric to final weighted scores.
The seeded data (balanced/growth/dividend) was historically broken (#64)
because profile_metric_settings was empty — profiles always fell back to
default weights and scored identically.
"""

import pytest

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository
from core.evaluation import evaluate_metric
from core.profiles import get_profile_weights
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
