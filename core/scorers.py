import math


def calculate_sigmoid_score(val: float, best: float, worst: float) -> float:
	"""
	Calculate a score based on a sigmoid (S-curve) function.

	The score is approximately 0.95 at 'best' and 0.05 at 'worst'.
	It smoothly transitions between them, saturating at 1.0 and 0.0.
	This is ideal for metrics where more is better (or less is better)
	with diminishing returns at extremes.

	Args:
		val (float): The raw value to score.
		best (float): The value that should result in a high score (~0.95).
		worst (float): The value that should result in a low score (~0.05).

	Returns:
		float: A score between 0.0 and 1.0.
	"""
	midpoint = (best + worst) / 2
	try:
		k = math.log(1 / 19) / (best - midpoint)
		# Use k * (val - midpoint) directly.
		# If k is negative (best > worst), score increases with val.
		# If k is positive (best < worst), score decreases with val.
		score = 1 / (1 + math.exp(k * (val - midpoint)))
	except (ZeroDivisionError, ValueError, OverflowError):
		# Fallback for degenerate cases or extreme overflows
		if abs(best - worst) < 1e-9:
			return 1.0 if val >= best else 0.0

		# If it overflows, it's either very large or very small
		# exp(large positive) -> score 0
		# exp(large negative) -> score 1
		# Check k calculation to determine direction
		try:
			k_dir = math.log(1 / 19) / (best - midpoint)
			return 1.0 if (k_dir * (val - midpoint)) < 0 else 0.0
		except (ZeroDivisionError, ValueError):
			return 1.0 if val == best else 0.0
	return score


def calculate_linear_score(val: float, best: float, worst: float) -> float:
	"""
	Linear scoring between best and worst.

	Args:
		val (float): The raw value to score.
		best (float): The value that results in 1.0.
		worst (float): The value that results in 0.0.

	Returns:
		float: A score between 0.0 and 1.0, clipped.
	"""
	if abs(best - worst) < 1e-9:
		return 1.0 if val >= best else 0.0

	if best > worst:  # Higher is better (e.g. ROE)
		pct = (val - worst) / (best - worst)
	else:  # Lower is better (e.g. P/E)
		pct = (worst - val) / (worst - best)

	return max(-1.0, min(1.0, pct))


def calculate_bell_score(val: float, target: float, width: float) -> float:
	"""
	Gaussian scoring for 'Goldilocks' metrics.

	Args:
		val (float): The raw value to score.
		target (float): The ideal value (results in 1.0).
		width (float): The standard deviation-like parameter controlling decay.

	Returns:
		float: A score between 0.0 and 1.0.
	"""
	try:
		return math.exp(-0.5 * ((val - target) / width) ** 2)
	except (ZeroDivisionError, OverflowError):
		return 0.0


def calculate_plateau_score(
	val: float, target_min: float, target_max: float, width: float
) -> float:
	"""
	Plateau scoring for a 'sweet spot' range.

	Returns 1.0 if val is between target_min and target_max.
	Otherwise, decays using a Gaussian curve from the nearest edge.

	Args:
		val (float): The raw value to score.
		target_min (float): Lower bound of the ideal range.
		target_max (float): Upper bound of the ideal range.
		width (float): The decay rate outside the ideal range.

	Returns:
		float: A score between 0.0 and 1.0.
	"""
	if target_min <= val <= target_max:
		return 1.0

	edge = target_min if val < target_min else target_max
	try:
		return math.exp(-0.5 * ((val - edge) / width) ** 2)
	except (ZeroDivisionError, OverflowError):
		return 0.0


def calculate_threshold_score(val: float, threshold: float) -> float:
	"""
	Binary pass/fail threshold.

	Args:
		val (float): The raw value.
		threshold (float): Minimum value for 1.0.

	Returns:
		float: 1.0 if val >= threshold, else 0.0.
	"""
	return 1.0 if val >= threshold else 0.0


def calculate_penalty_threshold_score(
	val: float, threshold: float, worst: float
) -> float:
	"""
	Returns 0.0 if val is better than threshold.
	If val is worse than threshold, returns a negative value proportional
	to how far it exceeds the threshold, capped at -1.0.

	Args:
		val (float): The raw value to score.
		threshold (float): The value where penalties begin (returns 0.0).
		worst (float): The value where the maximum penalty is reached (returns -1.0).

	Returns:
		float: A score between -1.0 and 0.0.
	"""
	if abs(worst - threshold) < 1e-9:
		return -1.0 if val >= threshold else 0.0

	# Direction: if worst > threshold, val must be > threshold to penalise
	if worst > threshold:
		if val <= threshold:
			return 0.0
		pct = (val - threshold) / (worst - threshold)
	else:
		if val >= threshold:
			return 0.0
		pct = (threshold - val) / (threshold - worst)

	return -max(0.0, min(1.0, pct))


def calculate_flat_penalty_score(
	val: float, threshold: float, penalty_value: float = -0.5
) -> float:
	"""
	Binary penalty: if threshold met, return fixed negative value.

	Args:
		val (float): The raw value.
		threshold (float): The value at which the penalty is triggered.
		penalty_value (float): The fixed score to return if triggered.

	Returns:
		float: penalty_value or 0.0.
	"""
	# Check if threshold is a 'ceiling' (worst case) or 'floor'
	# For simplicity, we assume 'at least threshold' triggers penalty
	return penalty_value if val >= threshold else 0.0


# Registry for easy extension
SCORERS = {
	"sigmoid": calculate_sigmoid_score,
	"linear": calculate_linear_score,
	"bell_curve": calculate_bell_score,
	"plateau": calculate_plateau_score,
	"threshold": calculate_threshold_score,
	"penalty_threshold": calculate_penalty_threshold_score,
	"flat_penalty": calculate_flat_penalty_score,
}
