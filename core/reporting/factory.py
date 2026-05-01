import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .csv_reporter import CSVReporter
from .txt_reporter import TXTReporter


def generate_report(
	results: List[Dict[str, Any]],
	fmt: str,
	tickers: List[str],
	index_name: Optional[str] = None,
	base_dir: str = "reports",
) -> str:
	"""
	Generates a report file with an automated name and returns the path.
	Name format: <IDENTIFIER>_<YYYYMMDD_HHMMSS>.<ext>
	"""
	if not os.path.exists(base_dir):
		os.makedirs(base_dir)

	# Determine the identifier
	if index_name:
		identifier = index_name.upper()
	elif len(tickers) == 1:
		identifier = tickers[0].upper()
	else:
		identifier = f"portfolio_{len(tickers)}"

	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	extension = fmt.lower()
	filename = f"{identifier}_{timestamp}.{extension}"
	output_path = os.path.join(base_dir, filename)

	if extension == "csv":
		reporter = CSVReporter()
	elif extension == "txt":
		reporter = TXTReporter()
	else:
		raise ValueError(f"Unsupported report format: {fmt}")

	reporter.export(results, output_path)
	return output_path
