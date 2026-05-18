import io
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

from .base import BaseReporter


class TXTReporter(BaseReporter):
	def export(
		self, all_results: List[Dict[str, Any]], output_path: str, profile: str = "N/A"
	):
		"""Export results to a plain text file mirroring terminal output."""
		if not all_results:
			return

		# Use a separate console to capture text output
		capture_console = Console(file=io.StringIO(), force_terminal=False, width=100)
		capture_console.print(
			f"FUNDAMENTAL ANALYSIS REPORT - {profile.upper()} PROFILE"
		)
		capture_console.print(f"{'=' * 50}\n")

		sorted_results = sorted(all_results, key=lambda x: x["score"], reverse=True)

		for i, res in enumerate(sorted_results):
			# Add a separator between tickers, but not before the first one
			if i > 0:
				capture_console.print("\n")

			capture_console.print(f"{'=' * 50}")
			capture_console.print(f"Analysis for {res['name']} ({res['symbol']})")
			capture_console.print(f"{'=' * 50}")

			table = Table(show_header=True, header_style="bold")
			table.add_column("Metric", style="dim")
			table.add_column("Value", justify="right")
			table.add_column("Strength", justify="right")
			table.add_column("Points", justify="right")

			for m in res["results"]:
				table.add_row(
					m["name"],
					str(m["value"]),
					m["status"],
					f"{m['score']:.2f}/{m['weight']:.1f}",
				)

			capture_console.print(table)
			capture_console.print(f"FINAL SCORE: {res['score']:.2f}%")

		with open(output_path, "w") as f:
			f.write(capture_console.file.getvalue())
