import csv
from typing import Any, Dict, List

from rich.console import Console

from .base import BaseReporter

console = Console()


class CSVReporter(BaseReporter):
	def export(
		self, all_results: List[Dict[str, Any]], output_path: str, profile: str = "N/A"
	):
		"""Export full results to a CSV file in horizontal format."""
		if not all_results:
			return

		# 1. Determine all unique benchmark names across all results
		benchmark_names = []
		for res in all_results:
			for metric in res.get("results", []):
				name = metric["name"]
				if name not in benchmark_names:
					benchmark_names.append(name)

		# 2. Build Headers
		headers = ["Symbol", "Name", "Profile", "Asset Type", "Total Score (%)"]
		for name in benchmark_names:
			headers.append(f"{name} (Value)")
			headers.append(f"{name} (Strength %)")

		try:
			with open(output_path, "w", newline="") as f:
				writer = csv.DictWriter(f, fieldnames=headers)
				writer.writeheader()

				for res in all_results:
					# Handle asset_type as Enum or string
					asset_type = res.get("asset_type")
					asset_type_str = (
						str(asset_type.value)
						if hasattr(asset_type, "value")
						else (str(asset_type) if asset_type is not None else "")
					)

					row = {
						"Symbol": res["symbol"],
						"Name": res["name"],
						"Profile": profile.upper(),
						"Asset Type": asset_type_str,
						"Total Score (%)": f"{res['score']:.2f}",
					}

					metric_map = {m["name"]: m for m in res.get("results", [])}
					for name in benchmark_names:
						metric_data = metric_map.get(name)
						if metric_data:
							row[f"{name} (Value)"] = metric_data["value"]
							row[f"{name} (Strength %)"] = metric_data["status"].replace(
								"%", ""
							)
						else:
							row[f"{name} (Value)"] = "N/A"
							row[f"{name} (Strength %)"] = "N/A"

					writer.writerow(row)

		except Exception as e:
			raise RuntimeError(f"Failed to export CSV: {e}")
