import sqlite3
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def get_db_conn():
	db_path = Path("market_analysis.db")
	if not db_path.exists():
		console.print("[bold red]Error: Database file not found.[/bold red]")
		return None
	conn = sqlite3.connect(str(db_path))
	conn.row_factory = sqlite3.Row
	return conn


def show_assets():
	conn = get_db_conn()
	if not conn:
		return

	cursor = conn.cursor()
	cursor.execute(
		"SELECT symbol, name, asset_type, sector, last_updated FROM assets LIMIT 20"
	)
	rows = cursor.fetchall()

	table = Table(title="Assets (Metadata)")
	table.add_column("Symbol", style="cyan")
	table.add_column("Name", style="green")
	table.add_column("Type", style="magenta")
	table.add_column("Sector", style="yellow")
	table.add_column("Last Updated", style="dim")

	for row in rows:
		table.add_row(
			row["symbol"],
			row["name"] or "N/A",
			row["asset_type"] or "N/A",
			row["sector"] or "N/A",
			row["last_updated"],
		)

	console.print(table)
	conn.close()


def show_indices():
	conn = get_db_conn()
	if not conn:
		return

	cursor = conn.cursor()
	cursor.execute("""
		SELECT i.symbol, i.last_updated, COUNT(c.asset_symbol) as count 
		FROM indices i
		LEFT JOIN index_constituents c ON i.symbol = c.index_symbol
		GROUP BY i.symbol
	""")
	rows = cursor.fetchall()

	table = Table(title="Indices & ETF Membership")
	table.add_column("Index Symbol", style="cyan")
	table.add_column("Constituents", justify="right", style="green")
	table.add_column("Last Updated", style="dim")

	for row in rows:
		table.add_row(row["symbol"], str(row["count"]), row["last_updated"])

	console.print(table)
	conn.close()


def show_snapshots():
	conn = get_db_conn()
	if not conn:
		return

	cursor = conn.cursor()
	cursor.execute(
		"SELECT symbol, timestamp, profile, total_score FROM analysis_snapshots ORDER BY timestamp DESC LIMIT 15"
	)
	rows = cursor.fetchall()

	table = Table(title="Latest Analysis Snapshots")
	table.add_column("Symbol", style="cyan")
	table.add_column("Time", style="dim")
	table.add_column("Profile", style="magenta")
	table.add_column("Score", justify="right", style="bold green")

	for row in rows:
		score_color = (
			"green"
			if row["total_score"] >= 70
			else "yellow"
			if row["total_score"] >= 50
			else "red"
		)
		table.add_row(
			row["symbol"],
			row["timestamp"],
			row["profile"],
			f"[{score_color}]{row['total_score']:.1f}%[/{score_color}]",
		)

	console.print(table)
	conn.close()


def show_sectors():
	conn = get_db_conn()
	if not conn:
		return

	cursor = conn.cursor()
	cursor.execute(
		"SELECT sector, metric_key, benchmark_type, value_a, value_b FROM sector_benchmarks ORDER BY sector, metric_key"
	)
	rows = cursor.fetchall()

	table = Table(title="Sector Benchmarks (30-day cache)")
	table.add_column("Sector", style="cyan")
	table.add_column("Metric", style="green")
	table.add_column("Type", style="magenta")
	table.add_column("Value A", justify="right")
	table.add_column("Value B", justify="right")

	for row in rows:
		table.add_row(
			row["sector"],
			row["metric_key"],
			row["benchmark_type"],
			f"{row['value_a']:.2f}",
			f"{row['value_b']:.2f}",
		)

	console.print(table)
	conn.close()


def show_profiles():
	conn = get_db_conn()
	if not conn:
		return

	cursor = conn.cursor()
	# Get profiles and their weight counts
	cursor.execute("""
		SELECT p.name, p.description, COUNT(w.metric_key) as weight_count
		FROM investor_profiles p
		LEFT JOIN profile_weights w ON p.name = w.profile_name
		GROUP BY p.name
	""")
	rows = cursor.fetchall()

	table = Table(title="Investor Profiles")
	table.add_column("Profile ID", style="cyan")
	table.add_column("Description", style="green")
	table.add_column("Weights", justify="right", style="magenta")

	for row in rows:
		table.add_row(
			row["name"], row["description"] or "N/A", str(row["weight_count"])
		)

	console.print(table)
	conn.close()


def show_benchmarks():
	conn = get_db_conn()
	if not conn:
		return

	cursor = conn.cursor()
	cursor.execute(
		"SELECT asset_type, metric_key, formula_type, weight, params_json FROM global_benchmarks ORDER BY asset_type, metric_key"
	)
	rows = cursor.fetchall()

	table = Table(title="Global Benchmarks (Core Rules)")
	table.add_column("Type", style="cyan")
	table.add_column("Metric", style="green")
	table.add_column("Formula", style="magenta")
	table.add_column("Weight", justify="right", style="yellow")
	table.add_column("Parameters", style="dim")

	for row in rows:
		table.add_row(
			row["asset_type"],
			row["metric_key"],
			row["formula_type"],
			f"{row['weight']:.1f}",
			row["params_json"],
		)

	console.print(table)
	conn.close()


def show_all_assets():
	conn = get_db_conn()
	if not conn:
		return

	cursor = conn.cursor()
	cursor.execute("SELECT symbol, name FROM assets ORDER BY symbol")
	rows = cursor.fetchall()

	table = Table(title=f"All Assets in DB ({len(rows)})")
	table.add_column("Symbol", style="cyan")
	table.add_column("Name", style="green")

	for row in rows:
		table.add_row(row["symbol"], row["name"] or "N/A")

	console.print(table)
	conn.close()


def dispatch_db_view(view: str):
	if view == "assets":
		show_assets()
	elif view == "indices":
		show_indices()
	elif view == "snapshots":
		show_snapshots()
	elif view == "sectors":
		show_sectors()
	elif view == "profiles":
		show_profiles()
	elif view == "benchmarks":
		show_benchmarks()
	elif view == "inventory":
		show_all_assets()
