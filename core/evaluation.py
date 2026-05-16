from typing import Any, Dict

from core.analysis.preprocessing import postprocess_score, preprocess_metric_value
from core.ui.formatters import format_display_value

from .schema import AssetData
from .scorers import SCORERS


def _resolve_params(
	formula_type: str,
	profile_setting: Dict[str, Any],
	benchmark: Dict[str, Any],
) -> Dict[str, Any]:
	"""
	Merge profile-level curve overrides onto benchmark defaults.

	Profile stores range_min/range_max as the two primary user-adjustable
	parameters. Their meaning depends on formula_type:
	sigmoid/linear → best/worst, bell_curve → target/width,
	plateau → target_min/target_max, threshold → threshold.

	Benchmark values are used as fallback when the profile has no override.

	Args:
		formula_type: Scoring formula name (e.g. 'sigmoid').
		profile_setting: Dict with 'best' (range_min) and 'worst' (range_max).
		benchmark: Static benchmark definition dict.

	Returns:
		Merged parameter dict ready for the scorer function.
	"""
	p_best = profile_setting.get("best")
	p_worst = profile_setting.get("worst")

	# (0.0, 100.0) is the seeder/default placeholder — not a real user customisation.
	# Treat it as "no override" so benchmark curve params are preserved.
	is_placeholder = p_best == 0.0 and p_worst == 100.0
	has_override = p_best is not None and p_worst is not None and not is_placeholder

	if not has_override:
		return benchmark

	params = dict(benchmark)
	if formula_type in ("sigmoid", "linear"):
		params["best"] = p_best
		params["worst"] = p_worst
	elif formula_type == "bell_curve":
		params["target"] = p_best
		params["width"] = p_worst
	elif formula_type == "plateau":
		params["target_min"] = p_best
		params["target_max"] = p_worst
	elif formula_type == "threshold":
		params["threshold"] = p_best
	return params


def evaluate_metric(
	asset: AssetData,
	benchmark: Dict[str, Any],
	profile_config: Dict[str, Any],
) -> Dict[str, Any]:
	"""
	Evaluate a single metric for an asset against its benchmark definition,
	honouring any profile-level curve overrides (formula, best, worst).

	Args:
		asset: Pre-loaded asset data object.
		benchmark: Static benchmark definition (metric key, formula type, params).
		profile_config: Per-metric config from get_profile_config. Each value is
			a dict with 'weight', 'best', 'worst', 'formula', or a plain
			float (legacy weight-only dict, handled for compatibility).

	Returns:
		Dict with metric, name, status, value, raw_value, score, weight, pct.
	"""
	metric_key = benchmark["metric"]

	# Support both new full-config dicts and legacy weight-only dicts
	raw_setting = profile_config.get(metric_key, {})
	if isinstance(raw_setting, (int, float)):
		p = {"weight": raw_setting}
	else:
		p = raw_setting

	weight = p.get("weight", 0.0)

	# Only override formula when a real range customisation is also present.
	# Without this guard, seeded placeholder formulas silently replace the
	# benchmark's formula_type (e.g. turning bell_curve → sigmoid).
	p_best_raw = p.get("best")
	p_worst_raw = p.get("worst")
	is_real_override = (
		p_best_raw is not None
		and p_worst_raw is not None
		and not (p_best_raw == 0.0 and p_worst_raw == 100.0)
	)
	formula_type = (p.get("formula") if is_real_override else None) or benchmark.get(
		"type", "sigmoid"
	)

	# Resolve scoring curve params — profile overrides take priority
	params = _resolve_params(formula_type, p, benchmark)

	unit = benchmark.get("unit")
	is_decimal = benchmark.get("is_decimal", False)

	raw_val = asset.get(metric_key)
	val = preprocess_metric_value(metric_key, raw_val, asset)

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

	display_val = format_display_value(val, unit, is_decimal)

	display_key = benchmark.get("display_key")
	if display_key and asset.get(display_key):
		label = str(asset.get(display_key)).replace("_", " ").title()
		display_val = f"{label} ({display_val})"

	scorer = SCORERS.get(formula_type)
	if not scorer:
		pct = 0.0
	elif formula_type == "sigmoid":
		pct = scorer(val, params.get("best", 0), params.get("worst", 100))
	elif formula_type == "linear":
		pct = scorer(val, params.get("best", 0), params.get("worst", 100))
	elif formula_type == "bell_curve":
		pct = scorer(val, params.get("target", 0), params.get("width", 1))
	elif formula_type == "plateau":
		pct = scorer(
			val,
			params.get("target_min", 0),
			params.get("target_max", 0),
			params.get("width", 1),
		)
	elif formula_type == "threshold":
		pct = scorer(val, params.get("threshold", 0))
	else:
		pct = 0.0

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
