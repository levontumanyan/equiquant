import os

from openbb import obb


def test_proxy():
	symbol = "AAPL"
	provider = "yfinance"

	print("--- Attempt 1: No proxy ---")
	try:
		res = obb.equity.fundamental.metrics(symbol=symbol, provider=provider)
		print(f"Success! Found {len(res.results)} results.")
	except Exception as e:
		print(f"Failed: {e}")

	print("\n--- Attempt 2: Fake proxy ---")
	os.environ["HTTP_PROXY"] = "http://1.2.3.4:5678"
	os.environ["HTTPS_PROXY"] = "http://1.2.3.4:5678"

	try:
		# We need to make sure the session is not reused if it was already created.
		# OpenBB Platform providers might cache sessions.
		res = obb.equity.fundamental.metrics(symbol=symbol, provider=provider)
		print(
			f"Success! Found {len(res.results)} results. (This is bad, it should have failed)"
		)
	except Exception as e:
		print(f"Expected failure: {e}")

	print("\n--- Attempt 3: No proxy again ---")
	del os.environ["HTTP_PROXY"]
	del os.environ["HTTPS_PROXY"]

	try:
		res = obb.equity.fundamental.metrics(symbol=symbol, provider=provider)
		print(f"Success! Found {len(res.results)} results.")
	except Exception as e:
		print(f"Failed: {e}")


if __name__ == "__main__":
	test_proxy()
