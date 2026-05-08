from core.analysis.reporting_expert import (
	detect_report_anomalies,
	extract_report_highlights,
	load_report_data,
)


def test_analysis():
	report_path = "reports/portfolio_4_20260504_221124.csv"
	data = load_report_data(report_path)

	if not data:
		print("No data found.")
		return

	highlights = extract_report_highlights(data)
	anomalies = detect_report_anomalies(data)

	print("--- HIGHLIGHTS ---")
	print(
		f"Top Performer: {highlights['top_performer']['Symbol']} ({highlights['top_performer']['Total Score (%)']}%)"
	)
	print(
		f"Bottom Performer: {highlights['bottom_performer']['Symbol']} ({highlights['bottom_performer']['Total Score (%)']}%)"
	)

	print("\n--- BEST IN CLASS (Sample) ---")
	for metric in ["Profit Margin", "Return on Equity", "Trailing P/E Ratio"]:
		if metric in highlights["best_in_class"]:
			bic = highlights["best_in_class"][metric]
			print(f"{metric}: {bic['symbol']} ({bic['value']} | {bic['strength']}%)")

	print("\n--- ANOMALIES ---")
	for a in anomalies:
		print(f"[{a['severity']}] {a['symbol']} - {a['type']}: {a['message']}")


if __name__ == "__main__":
	test_analysis()
