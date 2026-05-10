import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from core.stats import SessionStats

console = Console()


def get_color_for_pct(pct: float) -> str:
	if pct >= 0.9:
		return "bold green"
	if pct >= 0.7:
		return "green"
	if pct >= 0.4:
		return "yellow"
	return "red"


def display_individual_results(
	ticker_symbol: str,
	company_name: str,
	results: List[Dict[str, Any]],
	benchmark_defs: List[Dict[str, Any]],
	sector: Optional[str] = None,
	industry: Optional[str] = None,
):
	title = f"Analysis for {company_name} ({ticker_symbol})"
	if sector:
		title += f"\n[dim]{sector} | {industry}[/dim]"

	table = Table(title=title)
	table.add_column("Metric", style="cyan")
	table.add_column("Value", justify="right")
	table.add_column("Strength", justify="center")
	table.add_column("Points", justify="right")

	# Combine data for sorting
	display_data = []
	for res, b_def in zip(results, benchmark_defs):
		# Clarify specific metric names for readability
		friendly_name = b_def["name"]
		if friendly_name == "Current Ratio":
			friendly_name = "Current Ratio (Liquidity)"
		elif friendly_name == "Trailing P/E Ratio":
			friendly_name = "Trailing P/E (Past 12m)"
		elif friendly_name == "Forward P/E Ratio":
			friendly_name = "Forward P/E (Next 12m)"

		display_data.append(
			{
				"name": friendly_name,
				"value": res["value"],
				"status": res["status"],
				"score": res["score"],
				"weight": res["weight"],
				"pct": res["pct"],
			}
		)

	# Sort by weight descending (importance)
	display_data.sort(key=lambda x: x["weight"], reverse=True)

	total_score = total_weight = 0.0

	for item in display_data:
		if item["weight"] == 0:
			status_style = "dim"
			points_str = "N/A"
		else:
			status_style = get_color_for_pct(item["pct"])
			points_str = f"{item['score']:.2f}/{item['weight']:.1f}"

		table.add_row(
			item["name"],
			item["value"],
			f"[{status_style}]{item['status']}[/{status_style}]",
			points_str,
		)
		total_score += item["score"]
		total_weight += item["weight"]

	console.print(table)

	if total_weight > 0:
		final_pct = (total_score / total_weight) * 100
		color = (
			"bold green" if final_pct >= 70 else "yellow" if final_pct >= 40 else "red"
		)
		console.print(
			f"\n[bold]FINAL SCORE:[/bold] [{color}]{total_score:.2f}/{total_weight:.1f} ({final_pct:.1f}%)[/{color}]\n"
		)
	else:
		console.print("\n[bold red]Insufficient data to calculate score.[/bold red]\n")


def display_historical_scores(symbol: str, profile: str, snapshots: List[dict]):
	"""Display historical scores for a company and profile."""
	if not snapshots:
		console.print(
			f"[bold red]No historical data found for {symbol} with {profile} profile.[/bold red]"
		)
		return

	# Short labels for metrics to keep table width manageable
	metric_labels = {
		"current_ratio": "CR",
		"days_to_cover": "DTC",
		"debt_to_equity": "D/E",
		"dividend_yield": "DY",
		"ebitda_margin": "EBITDA%",
		"enterprise_to_ebitda": "EV/E",
		"forward_pe": "FPE",
		"insider_ownership": "Own.I",
		"institution_ownership": "Own.Inst",
		"pe_ratio": "PE",
		"peg_ratio": "PEG",
		"price_to_book": "P/B",
		"profit_margin": "PM%",
		"recommendation_mean": "Rec",
		"return_on_equity": "ROE",
		"revenue_growth": "Rev.G",
		"short_percent_of_float": "SPF",
	}

	table = Table(title=f"Historical Scores for {symbol} ({profile.upper()} profile)")
	table.add_column("Timestamp", style="dim")
	table.add_column("Total", justify="right")

	# Dynamically discover metric names from the latest snapshot's results_json
	try:
		latest_results = json.loads(snapshots[0]["results_json"])
		# Sort metrics by importance (weight) if available in JSON
		latest_results.sort(key=lambda x: x.get("weight", 0), reverse=True)

		# Limit to top 10 metrics to keep the table readable
		latest_results = latest_results[:10]

		metric_keys = [r["metric"] for r in latest_results]
		for key in metric_keys:
			label = metric_labels.get(key, key[:5])
			table.add_column(label, justify="right")
	except (json.JSONDecodeError, KeyError, IndexError):
		metric_keys = []

	for snap in snapshots:
		score = snap["total_score"]
		color = "bold green" if score >= 70 else "yellow" if score >= 40 else "red"

		# Shorten timestamp from YYYY-MM-DD HH:MM:SS to DD/MM/YY
		try:
			dt = datetime.strptime(snap["timestamp"], "%Y-%m-%d %H:%M:%S")
			ts_display = dt.strftime("%d/%m/%y")
		except (ValueError, TypeError):
			ts_display = snap["timestamp"][:8]

		row = [ts_display, f"[{color}]{score:.1f}%[/{color}]"]

		try:
			results_list = json.loads(snap["results_json"])
			# Create a map for easy lookup, handle missing 'pct' key
			results_map = {}
			for r in results_list:
				m_key = r["metric"]
				if "pct" in r:
					results_map[m_key] = r["pct"]
				elif r.get("weight", 0) > 0:
					results_map[m_key] = r["score"] / r["weight"]
				else:
					results_map[m_key] = 0.0

			for key in metric_keys:
				pct = results_map.get(key, 0.0)
				# Convert 0.0-1.0 to 0-100%
				pct_val = pct * 100
				pct_color = get_color_for_pct(pct)
				row.append(f"[{pct_color}]{pct_val:.0f}%[/{pct_color}]")
		except (json.JSONDecodeError, KeyError):
			row.extend(["N/A"] * len(metric_keys))

		table.add_row(*row)

	console.print(table)


def display_summary_table(all_results: List[Dict[str, Any]]):
	"""
	Display a summary table of all analyzed assets.
	"""
	table = Table(title="Analysis Summary")
	table.add_column("Symbol", style="cyan")
	table.add_column("Name", style="white")
	table.add_column("Score", justify="right", style="green")
	table.add_column("Verdict", style="bold")

	# Sort by score descending
	sorted_results = sorted(all_results, key=lambda x: x["score"], reverse=True)

	for res in sorted_results:
		score = res["score"]
		verdict = (
			"Strong Buy"
			if score > 80
			else "Buy"
			if score > 65
			else "Hold"
			if score > 40
			else "Avoid"
		)
		color = "green" if score > 65 else "yellow" if score > 40 else "red"

		table.add_row(
			res["symbol"],
			res["name"][:30],
			f"[{color}]{score:.1f}%[/{color}]",
			f"[{color}]{verdict}[/{color}]",
		)

	console.print(table)


def display_run_summary(stats: SessionStats):
	"""Display a summary of the execution run (timers, cache hits, etc)."""
	table = Table(title="Execution Run Summary", show_header=False, box=None)
	table.add_column("Metric", style="dim")
	table.add_column("Value", style="bold")

	# Duration metrics
	table.add_row("Total Duration", f"{stats.get_total_time():.2f}s")
	for stage, duration in stats.stage_times.items():
		table.add_row(f"  └─ {stage}", f"{duration:.2f}s")

	# Cache metrics
	total_requests = stats.cache_hits + stats.api_attempts
	cache_rate = (stats.cache_hits / total_requests * 100) if total_requests > 0 else 0
	table.add_row("Cache Hits", f"{stats.cache_hits} ({cache_rate:.1f}%)")
	table.add_row("API Attempts", str(stats.api_attempts))
	table.add_row("API Successes", str(stats.api_successes))
	table.add_row("HTTP Requests", str(stats.http_requests))

	if stats.errors > 0:
		table.add_row("Errors", f"[bold red]{stats.errors}[/bold red]")

	console.print("\n")
	console.print(table)
