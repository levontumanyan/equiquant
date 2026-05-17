import math
from typing import Any, Optional

from core.schema import AssetData


def preprocess_metric_value(
	metric_key: str, val: Any, asset: AssetData
) -> Optional[float]:
	"""
	Apply normalization and special handling for specific metrics.
	"""
	# Handle missing or non-numeric data
	if val is None:
		# Special fallback for dividend yield keys
		if metric_key in [
			"dividendYield",
			"trailingAnnualDividendYield",
			"yield",
			"trailingAnnualDividendRate",
		]:
			alt_keys = [
				"dividendYield",
				"trailingAnnualDividendYield",
				"yield",
				"trailingAnnualDividendRate",
			]
			for key in alt_keys:
				alt_val = asset.get(key)
				if alt_val is not None:
					val = float(alt_val)
					break

	if (
		val is None
		or not isinstance(val, (int, float))
		or (isinstance(val, float) and math.isnan(val))
	):
		return None

	# Convert to float
	val = float(val)

	# === SPECIAL HANDLING FOR INSTITUTIONAL OWNERSHIP ===
	if metric_key == "heldPercentInstitutions":
		val = min(val, 1.0)

	return val


def postprocess_score(metric_key: str, val: float, pct: float) -> float:
	"""
	Apply logic that overrides the calculated percentage score.
	"""
	# === SPECIAL HANDLING FOR NEGATIVE VALUATION RATIOS ===
	if metric_key in ["pegRatio", "trailingPE", "forwardPE"] and val < 0:
		return 0.0

	return pct
