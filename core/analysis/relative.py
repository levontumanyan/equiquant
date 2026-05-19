"""
Data-driven relative benchmark computation for sector-relative and batch-relative scoring.

Instead of static hardcoded thresholds, benchmarks are derived from the actual
distribution of metric values observed in a peer group (same sector, or the submitted batch).
"""

import statistics
from typing import Any, Dict, List

from core.schema import AssetData

MIN_PEERS_DEFAULT = 3


def _percentile(sorted_values: List[float], pct: float) -> float:
	"""
	Compute the pct-th percentile (0–100) from a pre-sorted list using linear interpolation.

	Args:
		sorted_values: Ascending-sorted list of floats (must be non-empty).
		pct: Percentile to compute, in [0, 100].

	Returns:
		Interpolated percentile value.
	"""
	n = len(sorted_values)
	if n == 1:
		return sorted_values[0]
	idx = pct / 100.0 * (n - 1)
	lo = int(idx)
	hi = min(lo + 1, n - 1)
	return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (idx - lo)


def extract_metric_values(
	assets: List[AssetData],
	metric_keys: List[str],
) -> Dict[str, List[float]]:
	"""
	Extract non-null numeric values for each metric key from a list of assets.

	Args:
		assets: List of AssetData objects to pull values from.
		metric_keys: Metric keys to extract.

	Returns:
		Dict mapping metric_key → list of non-null float values.
	"""
	result: Dict[str, List[float]] = {k: [] for k in metric_keys}
	for asset in assets:
		for key in metric_keys:
			val = asset.get(key)
			if val is not None:
				try:
					result[key].append(float(val))
				except (TypeError, ValueError):
					pass
	return result


def compute_relative_benchmarks(
	global_benchmarks: List[Dict[str, Any]],
	metric_values: Dict[str, List[float]],
	min_peers: int = MIN_PEERS_DEFAULT,
) -> List[Dict[str, Any]]:
	"""
	Derive benchmark parameters from the observed distribution of peer metric values.

	For each metric, the best/worst (or target/width) thresholds are replaced by
	percentile-based values computed from the peer group. Falls back to the global
	benchmark when fewer than min_peers data points are available, or for formula
	types where relative computation is not meaningful (e.g. threshold).

	Formula-specific strategy:
	sigmoid/linear: higher_is_better → best=P75, worst=P25; lower_is_better → best=P25, worst=P75.
	bell_curve: target=median, width=max((P75-P25)/2, eps).
	plateau: target_min=P33, target_max=P67.
	threshold: unchanged (absolute semantics, not distributional).

	Args:
		global_benchmarks: Full list of benchmark defs from the DB (global scope).
		metric_values: Dict of metric_key → sorted or unsorted list of peer floats.
		min_peers: Minimum number of non-null values required to apply relative logic.

	Returns:
		List of benchmark dicts with params replaced by peer-distribution values
		where applicable. Non-applicable metrics retain global params unchanged.
	"""
	result = []
	for bench in global_benchmarks:
		metric_key = bench["metric"]
		formula = bench.get("type", "sigmoid")

		values = sorted(v for v in metric_values.get(metric_key, []) if v is not None)

		if len(values) < min_peers or formula == "threshold":
			result.append(bench)
			continue

		override = dict(bench)

		if formula in ("sigmoid", "linear"):
			higher_is_better = bench.get("best", 1.0) > bench.get("worst", 0.0)
			if higher_is_better:
				override["best"] = _percentile(values, 75)
				override["worst"] = _percentile(values, 25)
			else:
				override["best"] = _percentile(values, 25)
				override["worst"] = _percentile(values, 75)

		elif formula == "bell_curve":
			override["target"] = statistics.median(values)
			q75 = _percentile(values, 75)
			q25 = _percentile(values, 25)
			override["width"] = max((q75 - q25) / 2.0, 1e-6)

		elif formula == "plateau":
			override["target_min"] = _percentile(values, 33)
			override["target_max"] = _percentile(values, 67)

		result.append(override)

	return result


def compute_batch_relative_benchmarks(
	assets: List[AssetData],
	global_benchmarks: List[Dict[str, Any]],
	min_peers: int = MIN_PEERS_DEFAULT,
) -> List[Dict[str, Any]]:
	"""
	Compute relative benchmarks from a submitted batch of assets.

	The batch itself defines the scoring reference frame: the best-performing
	stock in the batch on each metric anchors the top of the scale, and the
	worst-performing anchors the bottom. Useful for direct intra-batch ranking.

	Args:
		assets: All AssetData objects in the analysis batch.
		global_benchmarks: Global benchmark definitions (used for formula metadata).
		min_peers: Minimum assets with valid data for relative logic to engage.

	Returns:
		List of benchmark dicts derived from the batch distribution.
	"""
	metric_keys = [b["metric"] for b in global_benchmarks]
	values = extract_metric_values(assets, metric_keys)
	return compute_relative_benchmarks(global_benchmarks, values, min_peers)


def compute_sector_relative_benchmarks(
	sector: str,
	repo: Any,
	global_benchmarks: List[Dict[str, Any]],
	min_peers: int = MIN_PEERS_DEFAULT,
) -> List[Dict[str, Any]]:
	"""
	Compute relative benchmarks from all cached stocks in a given sector.

	Queries raw_provider_data joined against assets to gather sector peer values,
	normalises them via OpenBBProvider, then derives distributional benchmarks.
	Falls back to global benchmarks when the sector has fewer than min_peers cached stocks.

	Args:
		sector: Sector name (e.g. "Technology") to gather peer data for.
		repo: DatabaseRepository instance for querying sector peer data.
		global_benchmarks: Global benchmark definitions (used for formula metadata).
		min_peers: Minimum peer assets required to apply relative logic.

	Returns:
		List of benchmark dicts derived from the sector peer distribution.
	"""
	from core.providers.openbb_provider import OpenBBProvider

	peer_payloads = repo.get_sector_peer_raw_data(sector)
	if len(peer_payloads) < min_peers:
		return global_benchmarks

	provider = OpenBBProvider()
	assets = [
		provider._normalize(f"__PEER_{i}__", payload)
		for i, payload in enumerate(peer_payloads)
		if payload
	]
	assets = [a for a in assets if a is not None]

	if len(assets) < min_peers:
		return global_benchmarks

	metric_keys = [b["metric"] for b in global_benchmarks]
	values = extract_metric_values(assets, metric_keys)
	return compute_relative_benchmarks(global_benchmarks, values, min_peers)
