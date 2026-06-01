import math
from typing import Any, Optional

from core.metrics import INSTITUTION_OWNERSHIP, PE_FAMILY
from core.schema import AssetData


def preprocess_metric_value(
	metric_key: str, val: Any, asset: AssetData
) -> Optional[float]:
	"""
	Normalise and validate a raw metric value before scoring.

	Args:
		metric_key: Canonical metric key (from core.metrics).
		val: Raw value from AssetData.
		asset: Full asset object for cross-metric lookups.

	Returns:
		Cleaned float, or None if the value is missing or non-numeric.
	"""
	if (
		val is None
		or not isinstance(val, (int, float))
		or (isinstance(val, float) and math.isnan(val))
	):
		return None

	val = float(val)

	# Raw OpenBB institution_ownership can exceed 1.0 when reported as a
	# fraction rather than a percentage; cap to avoid artificially perfect scores.
	if metric_key == INSTITUTION_OWNERSHIP:
		val = min(val, 1.0)

	return val


def postprocess_score(metric_key: str, val: float, pct: float) -> float:
	"""
	Override a calculated score based on domain validity rules.

	Args:
		metric_key: Canonical metric key (from core.metrics).
		val: The raw numeric value that was scored.
		pct: The score produced by the formula (0.0–1.0).

	Returns:
		Adjusted score.
	"""
	# P/E family: negative earnings make the ratio mathematically undefined.
	# Industry convention (Bloomberg, FactSet) is N/A — score 0.
	if metric_key in PE_FAMILY and val < 0:
		return 0.0

	return pct
