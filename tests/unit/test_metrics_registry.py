"""
Validates that metric keys in seed files and provider maps stay in sync
with core.metrics. These tests are the enforcement mechanism — if a metric
is added to seeds without a constant, or a provider map drifts from the
canonical names, these fail at CI time rather than silently at runtime.
"""

import json
from pathlib import Path

import core.metrics as metrics
from core.providers.mappings import OPENBB_METRIC_MAP

SEEDS_DIR = Path(__file__).parent.parent.parent / "seeds"

_ALL_CONSTANTS: set = {
	v for k, v in vars(metrics).items() if isinstance(v, str) and not k.startswith("_")
}


def _load_seed_metric_keys(filename: str) -> set:
	"""Return the set of unique metric_key values from a seed JSON file."""
	data = json.loads((SEEDS_DIR / filename).read_text())
	return {row["metric_key"] for row in data}


def test_global_benchmarks_keys_have_constants():
	"""Every metric_key in global_benchmarks.json must have a constant in core.metrics."""
	seed_keys = _load_seed_metric_keys("global_benchmarks.json")
	missing = seed_keys - _ALL_CONSTANTS
	assert not missing, (
		f"metric_key values in global_benchmarks.json have no constant in core.metrics: {missing} — add them to core/metrics.py."
	)


def test_profile_metric_settings_keys_have_constants():
	"""Every metric_key in profile_metric_settings.json must have a constant in core.metrics."""
	seed_keys = _load_seed_metric_keys("profile_metric_settings.json")
	missing = seed_keys - _ALL_CONSTANTS
	assert not missing, (
		f"metric_key values in profile_metric_settings.json have no constant in core.metrics: {missing} — add them to core/metrics.py."
	)


def test_openbb_map_values_are_canonical():
	"""Every value in OPENBB_METRIC_MAP must be a constant in core.metrics."""
	non_canonical = set(OPENBB_METRIC_MAP.values()) - _ALL_CONSTANTS
	assert not non_canonical, (
		f"OPENBB_METRIC_MAP targets values not defined in core.metrics: {non_canonical} — add them to core/metrics.py or fix the mapping."
	)


def test_global_benchmarks_covered_by_openbb_map():
	"""
	Every scored metric in global_benchmarks.json should be reachable via
	OPENBB_METRIC_MAP, unless it comes from a non-OpenBB provider.
	Non-OpenBB metrics must be explicitly listed here so the gap is
	documented, not accidental.
	"""
	non_openbb_metrics = {
		metrics.NET_INCOME,
		metrics.DEBT_TO_EQUITY_PENALTY,
		metrics.OVERALL_RISK_PENALTY,
	}

	seed_keys = _load_seed_metric_keys("global_benchmarks.json")
	mapped_canonicals = set(OPENBB_METRIC_MAP.values())
	unmapped = seed_keys - mapped_canonicals - non_openbb_metrics
	assert not unmapped, (
		f"Scored metrics in global_benchmarks.json are not covered by OPENBB_METRIC_MAP and not listed as non-OpenBB: {unmapped} — add to OPENBB_METRIC_MAP or to non_openbb_metrics above."
	)
