from typing import Dict

from core.database.repository import DatabaseRepository


def get_profile_weights(
	repo: DatabaseRepository, profile_name: str = "balanced"
) -> Dict[str, float]:
	"""Return weight mapping for a given profile from the database"""
	settings = repo.get_profile_settings(profile_name.lower())
	weights = {setting["metric_key"]: setting["weight"] for setting in settings}

	if not weights:
		print(f"[Warning] Profile '{profile_name}' not found in DB. Using balanced.")
		settings = repo.get_profile_settings("balanced")
		weights = {setting["metric_key"]: setting["weight"] for setting in settings}
		if not weights:
			print(
				"[bold red]Error: 'balanced' profile also not found in DB. Cannot determine weights.[/bold red]"
			)
			return {}

	return weights
