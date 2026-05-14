import time
from pathlib import Path

import requests


def test_e2e_fetch():
	url = "http://localhost:8000/api/fetch"
	tickers = ["AAPL", "TSLA"]
	payload = {"tickers": tickers, "provider": "openbb"}

	print(f"🚀 Starting E2E fetch for {tickers}...")

	# Clear cache for these tickers to ensure a fresh fetch
	cache_dir = Path("cache") / "yfinance"
	for t in tickers:
		cache_file = cache_dir / f"{t}.json"
		if cache_file.exists():
			cache_file.unlink()
			print(f"🧹 Cleared cache for {t}")

	try:
		response = requests.post(url, json=payload, timeout=60)
		print(f"📥 Status Code: {response.status_code}")
		print(f"📄 Response: {response.json()}")

		if response.status_code == 200:
			# Verify files exist in cache
			time.sleep(2)  # Brief wait for I/O
			for t in tickers:
				cache_file = cache_dir / f"{t}.json"
				if cache_file.exists():
					print(f"✅ Verified: Cache file for {t} created successfully.")
				else:
					print(f"❌ Error: Cache file for {t} NOT found.")
		else:
			print("❌ API request failed.")

	except Exception as e:
		print(f"❌ Connection Error: {e}")


if __name__ == "__main__":
	test_e2e_fetch()
