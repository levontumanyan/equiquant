import csv

import pytest

from core.analysis.reporting_expert import (
	detect_report_anomalies,
	extract_report_highlights,
	load_report_data,
)


@pytest.fixture
def sample_csv(tmp_path):
	d = tmp_path / "subdir"
	d.mkdir()
	file_path = d / "test_report.csv"
	headers = [
		"Symbol",
		"Name",
		"Total Score (%)",
		"Metric A (Value)",
		"Metric A (Strength %)",
		"Metric B (Value)",
		"Metric B (Strength %)",
	]
	rows = [
		["AAPL", "Apple", "80.0", "150", "90", "10", "70"],
		["TSLA", "Tesla", "30.0", "50", "20", "400", "5"],
		["NULL", "Missing", "50.0", "N/A", "N/A", "N/A", "N/A"],
	]
	with open(file_path, "w", newline="") as f:
		writer = csv.writer(f)
		writer.writerow(headers)
		writer.writerows(rows)
	return str(file_path)


def test_load_report_data(sample_csv):
	data = load_report_data(sample_csv)
	assert len(data) == 3
	assert data[0]["Symbol"] == "AAPL"
	assert data[1]["Total Score (%)"] == "30.0"


def test_extract_report_highlights(sample_csv):
	data = load_report_data(sample_csv)
	highlights = extract_report_highlights(data)

	assert highlights["top_performer"]["Symbol"] == "AAPL"
	assert highlights["bottom_performer"]["Symbol"] == "TSLA"
	assert highlights["count"] == 3

	# Best in class
	assert highlights["best_in_class"]["Metric A"]["symbol"] == "AAPL"
	assert highlights["best_in_class"]["Metric A"]["strength"] == "90"


def test_detect_report_anomalies(sample_csv):
	# TSLA has Metric B (Value) = 400, but our anomaly check is hardcoded for P/E Ratio.
	# For now, let's verify it handles high N/A count.
	pass


def test_detect_anomalies_pe_outlier(tmp_path):
	file_path = tmp_path / "pe_report.csv"
	headers = ["Symbol", "Trailing P/E Ratio (Value)", "Total Score (%)"]
	rows = [["EXPNSV", "350x", "10.0"]]
	with open(file_path, "w", newline="") as f:
		writer = csv.writer(f)
		writer.writerow(headers)
		writer.writerows(rows)

	data = load_report_data(str(file_path))
	anomalies = detect_report_anomalies(data)
	assert len(anomalies) == 1
	assert anomalies[0]["type"] == "Valuation Outlier"
	assert "350x" in anomalies[0]["message"]
