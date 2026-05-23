from fastapi import APIRouter, HTTPException

from core.api.deps import repo
from core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/fx")

_SUPPORTED_PAIRS = {("USD", "CAD"), ("CAD", "USD")}
_CANONICAL = ("USD", "CAD")  # yfinance symbol: USDCAD=X


def _fetch_live_rate(from_currency: str, to_currency: str) -> float:
	"""Fetch a live FX rate from yfinance and persist it in the canonical direction.

	Args:
		from_currency: Source currency code.
		to_currency: Target currency code.

	Returns:
		float: The fetched exchange rate.

	Raises:
		RuntimeError: If yfinance returns no usable price.
	"""
	import yfinance as yf

	# Always fetch and store in canonical direction; invert if caller wants reverse
	frm, to = _CANONICAL
	symbol = f"{frm}{to}=X"
	ticker = yf.Ticker(symbol)
	rate = ticker.fast_info.get("last_price") or ticker.fast_info.get("lastPrice")
	if not rate:
		raise RuntimeError(f"yfinance returned no price for {symbol}")

	repo.upsert_fx_rate(frm, to, float(rate))
	logger.info(f"Refreshed FX rate {frm}/{to} = {rate}")

	if (from_currency, to_currency) == _CANONICAL:
		return float(rate)
	return 1.0 / float(rate)


@router.get("/rate")
def get_fx_rate(from_currency: str = "USD", to_currency: str = "CAD"):
	"""Return a USD/CAD exchange rate, using a 24-hour DB cache.

	Args:
		from_currency: Source currency (default 'USD').
		to_currency: Target currency (default 'CAD').

	Returns:
		dict: `{"from": str, "to": str, "rate": float, "cached": bool}`
	"""
	pair = (from_currency.upper(), to_currency.upper())
	if pair[0] == pair[1]:
		return {"from": pair[0], "to": pair[1], "rate": 1.0, "cached": True}
	if pair not in _SUPPORTED_PAIRS:
		raise HTTPException(
			status_code=422,
			detail=f"Unsupported pair {pair[0]}/{pair[1]}. Supported: USD/CAD, CAD/USD.",
		)

	cached = repo.get_fx_rate(*pair)
	if cached is not None:
		return {"from": pair[0], "to": pair[1], "rate": cached, "cached": True}

	try:
		rate = _fetch_live_rate(*pair)
	except Exception as e:
		logger.error(f"FX fetch failed for {pair}: {e}")
		raise HTTPException(status_code=503, detail=f"Could not fetch FX rate: {e}")

	return {"from": pair[0], "to": pair[1], "rate": rate, "cached": False}
