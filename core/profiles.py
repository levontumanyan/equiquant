from typing import Any, Dict

from core.database.repository import DatabaseRepository


def _load_settings(repo: DatabaseRepository, profile_name: str) -> list:
	"""Fetch raw profile_metric_settings rows, falling back to 'balanced'."""
	settings = repo.get_profile_settings(profile_name.lower())
	if not settings:
		print(f"[Warning] Profile '{profile_name}' not found in DB. Using balanced.")
		settings = repo.get_profile_settings("balanced")
		if not settings:
			print(
				"[Error] 'balanced' profile also not found in DB. Cannot determine weights."
			)
	return settings


def get_profile_config(
	repo: DatabaseRepository, profile_name: str = "balanced"
) -> Dict[str, Dict[str, Any]]:
	"""
	Return full per-metric configuration for a profile.

	Each entry contains weight plus the user-customised scoring parameters
	(range_min → best/target_min/target/threshold, range_max → worst/target_max/width)
	so evaluate_metric can honour profile-level curve overrides.

	Args:
		repo: Database repository instance.
		profile_name: Name of the investor profile to load.

	Returns:
		Dict mapping metric_key to {'weight', 'best', 'worst', 'formula'}.
	"""
	settings = _load_settings(repo, profile_name)
	return {
		s["metric_key"]: {
			"weight": s["weight"],
			"best": s["range_min"],
			"worst": s["range_max"],
			"formula": s["formula"],
			"is_penalty": bool(s.get("is_penalty", False)),
		}
		for s in settings
	}


def get_profile_weights(
	repo: DatabaseRepository, profile_name: str = "balanced"
) -> Dict[str, float]:
	"""
	Return weight-only mapping for a given profile (backward-compatible).

	Prefer get_profile_config for new code; this function is retained so
	existing tests and callers do not need updating.

	Args:
		repo: Database repository instance.
		profile_name: Name of the investor profile to load.

	Returns:
		Dict mapping metric_key to weight float.
	"""
	settings = _load_settings(repo, profile_name)
	return {s["metric_key"]: s["weight"] for s in settings}
