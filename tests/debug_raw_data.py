import sys


def debug_raw_profile(symbol):
	"""Investigate raw OpenBB endpoints for a given symbol."""
	print(f"Investigating endpoints for {symbol}...")
	from openbb import obb

	provider = "yfinance"

	endpoints = [
		(obb.equity.fundamental.metrics, "Fundamental Metrics"),
		(obb.equity.profile, "Company Profile"),
		(obb.equity.estimates.consensus, "Analyst Consensus"),
		(obb.equity.ownership.share_statistics, "Share Statistics"),
	]

	for func, label in endpoints:
		print(f"\n--- {label} ---")
		try:
			res = func(symbol=symbol, provider=provider)
			if res and res.results:
				data = res.results[0].model_dump()
				name_val = data.get("name")
				print(f"Name field: {name_val}")
				if name_val is None:
					print(f"WARNING: {label} returns NULL for name.")
			else:
				print(f"No results for {label}")
		except Exception as e:
			print(f"Error fetching {label}: {e}")


if __name__ == "__main__":
	ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
	debug_raw_profile(ticker)
