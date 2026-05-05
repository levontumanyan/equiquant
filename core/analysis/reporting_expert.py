import csv
import os
from typing import Any, Dict, List


def load_report_data(file_path: str) -> List[Dict[str, str]]:
	"""Loads CSV report data into a list of dictionaries."""
	if not os.path.exists(file_path):
		return []

	with open(file_path, mode="r", encoding="utf-8") as f:
		reader = csv.DictReader(f)
		return list(reader)


def extract_report_highlights(data: List[Dict[str, str]]) -> Dict[str, Any]:
	"""
	Extracts high-level highlights like top/bottom performers
	and best metrics across the set.
	"""
	if not data:
		return {}

	# Sort by Total Score
	sorted_by_score = sorted(
		data, key=lambda x: float(x.get("Total Score (%)", 0)), reverse=True
	)

	highlights = {
		"top_performer": sorted_by_score[0],
		"bottom_performer": sorted_by_score[-1],
		"count": len(data),
	}

	# Find "Best in Class" for each metric
	# (Look for columns ending in '(Strength %)')
	metric_strengths = [c for c in data[0].keys() if "(Strength %)" in c]
	best_in_class = {}

	for metric in metric_strengths:
		try:
			winner = max(
				data,
				key=lambda x: (
					float(x.get(metric, 0)) if x.get(metric) != "N/A" else -1.0
				),
			)
			if winner.get(metric) != "N/A":
				clean_name = metric.replace(" (Strength %)", "")
				best_in_class[clean_name] = {
					"symbol": winner["Symbol"],
					"strength": winner[metric],
					"value": winner.get(f"{clean_name} (Value)", "N/A"),
				}
		except (ValueError, TypeError):
			continue

	highlights["best_in_class"] = best_in_class
	return highlights


def detect_report_anomalies(data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
	"""
	Flags data gaps or extreme outliers in the report.
	"""
	anomalies = []

	for row in data:
		symbol = row["Symbol"]

		# 1. Check for N/As
		nas = [k for k, v in row.items() if v == "N/A"]
		if len(nas) > 5:  # Arbitrary threshold for "Low Confidence"
			anomalies.append(
				{
					"symbol": symbol,
					"type": "Data Gap",
					"severity": "High",
					"message": f"Asset has {len(nas)} missing metrics. Score confidence is low.",
				}
			)

		# 2. Check for extreme valuation outliers (Hardcoded for common ones)
		pe_val = row.get("Trailing P/E Ratio (Value)", "N/A")
		if pe_val != "N/A":
			try:
				pe_float = float(pe_val.replace("x", ""))
				if pe_float > 200:
					anomalies.append(
						{
							"symbol": symbol,
							"type": "Valuation Outlier",
							"severity": "Medium",
							"message": f"Extreme P/E Ratio ({pe_val}). Verify if this is a hyper-growth stock or data error.",
						}
					)
			except ValueError:
				pass

	return anomalies
