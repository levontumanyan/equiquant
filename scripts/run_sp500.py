"""
Diagnostic script: fire a full S&P 500 streaming analysis against the local API
and print SSE events with wall-clock timestamps.

Usage:
    uv run python scripts/run_sp500.py [--context global|batch|sector] [--profile balanced]
"""

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime

BASE_URL = "http://localhost:8000"


def ts() -> str:
	"""Return a short HH:MM:SS.mmm timestamp."""
	return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def get_sp500_tickers() -> list[str]:
	"""Fetch S&P 500 tickers from the groups API."""
	url = f"{BASE_URL}/api/groups/S%26P%20500/tickers"
	with urllib.request.urlopen(url, timeout=10) as resp:
		data = json.loads(resp.read())
	tickers = data if isinstance(data, list) else data.get("tickers", [])
	return [t.strip().upper() for t in tickers if t.strip()]


def stream_analysis(
	tickers: list[str], context: str, profile: str, force_refresh: bool = False
) -> None:
	"""POST tickers to the streaming endpoint and print SSE events."""
	payload = json.dumps(
		{
			"tickers": tickers,
			"profile": profile,
			"context": context,
			"force_refresh": force_refresh,
		}
	).encode()

	req = urllib.request.Request(
		f"{BASE_URL}/api/analyze/stream",
		data=payload,
		headers={
			"Content-Type": "application/json",
			"Accept": "text/event-stream",
		},
		method="POST",
	)

	analyzed = 0
	errors = 0
	start = time.perf_counter()
	event_type = None

	print(
		f"\n[{ts()}] Starting S&P 500 analysis — {len(tickers)} tickers, context={context}, profile={profile}"
	)
	print("-" * 72)

	with urllib.request.urlopen(req, timeout=3600) as resp:
		for raw_line in resp:
			line = raw_line.decode().rstrip()
			if not line:
				event_type = None
				continue

			if line.startswith("event:"):
				event_type = line[6:].strip()
				continue

			if line.startswith("data:"):
				raw_data = line[5:].strip()
				try:
					payload_obj = json.loads(raw_data)
				except json.JSONDecodeError:
					print(f"[{ts()}] RAW: {line}")
					continue

				if event_type == "status":
					msg = payload_obj.get("message", "")
					print(f"[{ts()}] STATUS  {msg}")

				elif event_type == "result":
					analyzed += 1
					symbol = payload_obj.get("symbol", "?")
					score = payload_obj.get("score")
					score_str = (
						f"{score:>6.1f}"
						if isinstance(score, (int, float))
						else f"{'?':>6}"
					)
					sector = payload_obj.get("sector") or ""
					elapsed = time.perf_counter() - start
					rate = analyzed / elapsed if elapsed > 0 else 0
					eta = (len(tickers) - analyzed) / rate if rate > 0 else 0
					print(
						f"[{ts()}] RESULT  {symbol:<6} score={score_str}  {sector:<30}  #{analyzed}/{len(tickers)}  rate={rate:.1f}/s  ETA={eta:.0f}s"
					)

				elif event_type == "error":
					errors += 1
					msg = payload_obj.get("message", raw_data)
					print(f"[{ts()}] ERROR   {msg}", file=sys.stderr)

				elif event_type == "done":
					total_time = time.perf_counter() - start
					print("-" * 72)
					print(
						f"[{ts()}] DONE    analyzed={payload_obj.get('analyzed')}/{payload_obj.get('total')}  errors={errors}  elapsed={total_time:.1f}s  avg={(total_time / analyzed if analyzed else 0):.2f}s/ticker"
					)

				else:
					print(f"[{ts()}] [{event_type}] {raw_data[:120]}")


def main() -> None:
	"""Parse args, fetch tickers, and run the streaming analysis."""
	parser = argparse.ArgumentParser(description="Run S&P 500 streaming analysis")
	parser.add_argument(
		"--context", default="global", choices=["global", "batch", "sector"]
	)
	parser.add_argument("--profile", default="balanced")
	parser.add_argument(
		"--limit", type=int, default=0, help="Limit to first N tickers (0 = all)"
	)
	parser.add_argument(
		"--force-refresh",
		action="store_true",
		help="Bypass DB cache and fetch fresh data",
	)
	args = parser.parse_args()

	print(f"[{ts()}] Fetching S&P 500 tickers from {BASE_URL}…")
	tickers = get_sp500_tickers()
	print(f"[{ts()}] Got {len(tickers)} tickers")

	if args.limit > 0:
		tickers = tickers[: args.limit]
		print(f"[{ts()}] Limited to first {len(tickers)} tickers")

	stream_analysis(
		tickers,
		context=args.context,
		profile=args.profile,
		force_refresh=args.force_refresh,
	)


if __name__ == "__main__":
	main()
