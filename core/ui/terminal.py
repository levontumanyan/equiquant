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
	"""Display a detailed summary of the execution run (diagnostics, telemetry, efficiency)."""
	console.print("\n")

	# 1. High-Level Performance
	perf_table = Table(title="Performance & I/O Telemetry", box=None, show_header=False)
	perf_table.add_column("Metric", style="dim")
	perf_table.add_column("Value", style="bold")

	total_time = stats.get_total_time()
	perf_table.add_row("Total Duration", f"{total_time:.2f}s")
	perf_table.add_row(
		"  └─ Network I/O",
		f"{stats.io_time_total:.2f}s ({stats.io_time_total / total_time * 100:.1f}%)",
	)
	perf_table.add_row(
		"  └─ Local Scoring",
		f"{stats.scoring_time_total:.2f}s ({stats.scoring_time_total / total_time * 100:.1f}%)",
	)
	if stats.cooldown_time_total > 0:
		perf_table.add_row(
			"  └─ Backpressure Cooldown",
			f"[bold yellow]{stats.cooldown_time_total:.2f}s[/bold yellow]",
		)

	console.print(perf_table)

	# 2. Endpoint Granularity
	if stats.endpoint_counts:
		ep_table = Table(title="Endpoint Granularity", header_style="bold cyan")
		ep_table.add_column("Endpoint")
		ep_table.add_column("Calls", justify="right")
		ep_table.add_column("Avg Latency", justify="right")

		# Sort by calls descending
		for ep in sorted(
			stats.endpoint_counts, key=stats.endpoint_counts.get, reverse=True
		):
			count = stats.endpoint_counts[ep]
			latencies = stats.endpoint_latencies.get(ep, [])
			avg_lat = sum(latencies) / len(latencies) if latencies else 0
			ep_table.add_row(ep, str(count), f"{avg_lat:.3f}s")

		console.print(ep_table)

	# 3. Data Quality / Coverage
	if stats.data_coverage:
		coverage_table = Table(
			title="Data Quality Audit (Coverage Density)", header_style="bold magenta"
		)
		coverage_table.add_column("Metric Key")
		coverage_table.add_column("Density", justify="right")
		coverage_table.add_column("Missing", justify="right")

		for metric, counts in sorted(stats.data_coverage.items()):
			total = counts["present"] + counts["missing"]
			density = (counts["present"] / total * 100) if total > 0 else 0
			color = "green" if density >= 95 else "yellow" if density >= 80 else "red"
			coverage_table.add_row(
				metric,
				f"[{color}]{density:.1f}%[/{color}]",
				f"[dim]{counts['missing']}[/dim]" if counts["missing"] > 0 else "0",
			)

		console.print(coverage_table)

	# 4. Error & Retry Summary
	error_data = stats.to_dict()
	if stats.errors > 0 or stats.retry_attempts > 0:
		err_table = Table(
			title="Error Topology & Resilience", box=None, show_header=False
		)
		err_table.add_column("Metric", style="dim")
		err_table.add_column("Value", style="bold")

		if stats.errors > 0:
			err_table.add_row("Total Errors", f"[bold red]{stats.errors}[/bold red]")
			for err_type, count in stats.error_types.items():
				err_table.add_row(f"  └─ {err_type}", str(count))

		if stats.retry_attempts > 0:
			retry_rate = error_data.get("retry_success_rate_pct", 0)
			color = (
				"green" if retry_rate >= 80 else "yellow" if retry_rate >= 50 else "red"
			)
			err_table.add_row(
				"Retry Success Rate",
				f"[{color}]{retry_rate:.1f}%[/{color}] ({stats.retry_successes}/{stats.retry_attempts})",
			)

		console.print(err_table)

	# 5. Efficiency & Resources
	eff_table = Table(
		title="Efficiency & Resource Footprint", box=None, show_header=False
	)
	eff_table.add_column("Metric", style="dim")
	eff_table.add_column("Value", style="bold")

	# Cache/Batching
	total_reqs = stats.cache_hits + stats.api_attempts
	cache_rate = (stats.cache_hits / total_reqs * 100) if total_reqs > 0 else 0
	eff_table.add_row("Cache Hit Rate", f"{cache_rate:.1f}% ({stats.cache_hits} hits)")

	batch_data = error_data.get("batching", {})
	bulk_ratio = batch_data.get("bulk_ratio_pct", 0)
	eff_table.add_row(
		"Bulk Fetch Ratio",
		f"{bulk_ratio:.1f}% ({batch_data.get('bulk_symbols', 0)} symbols)",
	)

	# DB Growth
	res_data = error_data.get("resource_footprint", {})
	db_growth = res_data.get("db_growth_bytes", 0)
	if db_growth > 0:
		eff_table.add_row("DB Growth", f"+{db_growth / 1024:.1f} KB")

	snapshots = res_data.get("db_snapshots", 0)
	if snapshots > 0:
		eff_table.add_row("DB Snapshots", str(snapshots))

	console.print(eff_table)

	# 6. Artifacts
	if stats.artifacts:
		console.print("\n[dim]Session Artifacts:[/dim]")
		for artifact in sorted(stats.artifacts):
			console.print(f"  [cyan]• {artifact}[/cyan]")

	console.print("\n")
