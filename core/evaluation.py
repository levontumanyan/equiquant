from typing import Any, Dict

from core.analysis.preprocessing import postprocess_score, preprocess_metric_value
from core.ui.formatters import format_display_value

from .schema import AssetData
from .scorers import SCORERS


def evaluate_metric(
	asset: AssetData, benchmark: Dict[str, Any], profile_weights: Dict[str, float]
) -> Dict[str, Any]:
	"""
	Evaluate a single metric for an asset against its benchmark definition.
	Returns formatted result with score.
	"""
	metric_key = benchmark["metric"]
	raw_val = asset.get(metric_key)
	default_weight = benchmark.get("weight", 1.0)
	formula_type = benchmark.get("type", "sigmoid")
	unit = benchmark.get("unit")
	is_decimal = benchmark.get("is_decimal", False)

	# Use profile weight if available, otherwise fallback to default
	weight = profile_weights.get(metric_key, default_weight)

	# Pre-process the value (normalization, special fallbacks)
	val = preprocess_metric_value(metric_key, raw_val, asset)

	# Handle missing or invalid data
	if val is None:
		return {
			"metric": metric_key,
			"name": benchmark["name"],
			"status": "N/A",
			"value": "N/A",
			"raw_value": None,
			"score": 0.0,
			"weight": 0.0,
			"pct": 0.0,
		}

	# Format value for display
	display_val = format_display_value(val, unit, is_decimal)

	# If benchmark specifies a display_key, use it to prefix the value (e.g. "Buy (1.89)")
	display_key = benchmark.get("display_key")
	if display_key and asset.get(display_key):
		label = str(asset.get(display_key)).replace("_", " ").title()
		display_val = f"{label} ({display_val})"

	# Calculate percentage score using the appropriate scorer
	scorer = SCORERS.get(formula_type)
	if not scorer:
		pct = 0.0
	elif formula_type == "sigmoid":
		pct = scorer(val, benchmark.get("best", 0), benchmark.get("worst", 100))
	elif formula_type == "linear":
		pct = scorer(val, benchmark.get("best", 0), benchmark.get("worst", 100))
	elif formula_type == "bell_curve":
		pct = scorer(val, benchmark.get("target", 0), benchmark.get("width", 1))
	elif formula_type == "plateau":
		pct = scorer(
			val,
			benchmark.get("target_min", 0),
			benchmark.get("target_max", 0),
			benchmark.get("width", 1),
		)
	elif formula_type == "threshold":
		pct = scorer(val, benchmark.get("threshold", 0))
	else:
		pct = 0.0

	# Post-process score (overrides for specific conditions like negative P/E)
	pct = postprocess_score(metric_key, val, pct)

	score = weight * pct

	return {
		"metric": metric_key,
		"name": benchmark["name"],
		"status": f"{pct * 100:.0f}%",
		"value": display_val,
		"raw_value": val,
		"score": score,
		"weight": weight,
		"pct": pct,
	}
