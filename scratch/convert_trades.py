import csv
import os
import sys
from datetime import datetime
from typing import Optional, Tuple

# Add the project root to sys.path so we can import core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository


def parse_amount(val_str: Optional[str]) -> Optional[float]:
	"""
	Parse a monetary or numeric string from the TSV row into a float.

	Removes currency symbols ($), commas, and surrounding whitespace.

	Parameters:
		val_str (Optional[str]): The raw string to parse.

	Returns:
		Optional[float]: The parsed float value, or None if the input is empty or invalid.
	"""
	if not val_str or not val_str.strip():
		return None
	# Remove $, commas, and whitespace
	cleaned = val_str.replace("$", "").replace(",", "").strip()
	try:
		return float(cleaned) if cleaned else None
	except ValueError:
		return None


def parse_date(date_raw: str) -> Optional[str]:
	"""
	Parse date from raw string and format as YYYY-MM-DD.

	Parameters:
		date_raw (str): The raw date string.

	Returns:
		Optional[str]: Formatted date string, or None.
	"""
	for fmt in ("%b %d, %Y", "%Y-%m-%d"):
		try:
			dt = datetime.strptime(date_raw.strip(), fmt)
			return dt.strftime("%Y-%m-%d")
		except ValueError:
			continue
	return None


def parse_tx_type(action_raw: Optional[str]) -> Optional[str]:
	"""
	Parse transaction type from raw action string.

	Parameters:
		action_raw (Optional[str]): Raw action string.

	Returns:
		Optional[str]: Transaction type ('BUY', 'SELL', 'DIVIDEND'), or None.
	"""
	if not action_raw:
		return None
	action = action_raw.strip().upper()
	if action in ("BUY", "BOUGHT"):
		return "BUY"
	if action in ("SELL", "SOLD"):
		return "SELL"
	if action in ("DIVIDEND", "DIV"):
		return "DIVIDEND"
	return None


def parse_dividend(
	row: dict, ticker: str, date_str: str
) -> Optional[Tuple[float, float, float]]:
	"""
	Parse dividend details from a TSV row, returning (quantity, price, total_amount).

	Parameters:
		row (dict): TSV row dictionary.
		ticker (str): Asset ticker symbol.
		date_str (str): Date of transaction.

	Returns:
		Optional[Tuple[float, float, float]]: (quantity, price, total_amount) tuple, or None.
	"""
	div_amount = parse_amount(row.get("Dividend Amount"))
	if div_amount is None:
		div_amount = parse_amount(row.get("Total Amount"))
	if div_amount is None or div_amount <= 0:
		print(f"Skipping dividend row for {ticker} on {date_str}: invalid amount")
		return None
	return 1.0, div_amount, div_amount


def parse_trade(
	row: dict, ticker: str, date_str: str
) -> Optional[Tuple[float, float, float]]:
	"""
	Parse buy/sell trade details from a TSV row, returning (quantity, price, total_amount).

	Parameters:
		row (dict): TSV row dictionary.
		ticker (str): Asset ticker symbol.
		date_str (str): Date of transaction.

	Returns:
		Optional[Tuple[float, float, float]]: (quantity, price, total_amount) tuple, or None.
	"""
	quantity = parse_amount(row.get("Quantity"))
	price = parse_amount(row.get("Price per Share"))
	total_amount = parse_amount(row.get("Total Amount"))

	if quantity is None or quantity <= 0:
		print(f"Skipping row for {ticker} on {date_str}: invalid quantity")
		return None

	if price is None or price <= 0:
		if total_amount is not None and total_amount > 0:
			price = total_amount / quantity
		else:
			print(
				f"Skipping row for {ticker} on {date_str}: price and total amount are missing"
			)
			return None

	if total_amount is None:
		total_amount = quantity * price

	return quantity, price, total_amount


def parse_row(row: dict) -> Optional[dict]:
	"""
	Parse a TSV row into a transaction dictionary.

	Parameters:
		row (dict): TSV row dictionary.

	Returns:
		Optional[dict]: Parsed transaction dictionary, or None.
	"""
	date_raw = row.get("Date")
	if not date_raw:
		return None

	date_str = parse_date(date_raw)
	if not date_str:
		print(f"Skipping row due to invalid date format: {date_raw}")
		return None

	tx_type = parse_tx_type(row.get("Action"))
	if not tx_type:
		print(f"Skipping row due to unknown action: {row.get('Action')}")
		return None

	ticker = row.get("Ticker", "").strip().upper()
	if not ticker:
		print("Skipping row: missing ticker symbol")
		return None
	if ticker == "GSI":
		ticker = "GSI.V"

	account = row.get("Account", "").strip()
	currency = row.get("Currency", "").strip() or "USD"
	bank = row.get("Bank", "").strip()
	total_cost_cad = parse_amount(row.get("Total Cost (CAD)"))

	if tx_type == "DIVIDEND":
		res = parse_dividend(row, ticker, date_str)
		if not res:
			return None
		quantity, price, total_amount = res
		div_amount = total_amount
	else:
		res = parse_trade(row, ticker, date_str)
		if not res:
			return None
		quantity, price, total_amount = res
		div_amount = None

	return {
		"symbol": ticker,
		"transaction_type": tx_type,
		"quantity": quantity,
		"price_per_share": price,
		"transaction_date": date_str,
		"fees": 0.0,
		"account": account,
		"bank": bank,
		"currency": currency,
		"total_amount": total_amount,
		"dividend_amount": div_amount,
		"total_cost_cad": total_cost_cad,
		"notes": None,
	}


def main() -> None:
	"""
	Main execution function to load trades from TSV, parse them, and write them to SQLite.
	"""
	tsv_path = "/Users/levontumanyan/.gemini/antigravity-cli/brain/d11930fd-c474-44ad-89cd-33e5484173a1/scratch/trades.tsv"
	if not os.path.exists(tsv_path):
		print(f"Error: trades.tsv not found at {tsv_path}")
		return

	print("Initializing Database Manager...")
	db_manager = DatabaseManager()
	repo = DatabaseRepository(db_manager)

	# Get or create a portfolio
	portfolios = repo.list_portfolios()
	portfolio_id = None

	if portfolios:
		print("\nExisting portfolios:")
		for p in portfolios:
			print(
				f"  ID: {p['id']} - Name: {p['name']} ({p.get('transaction_count', 0)} trades)"
			)

		portfolio_id = portfolios[0]["id"]
		print(
			f"Using existing portfolio: '{portfolios[0]['name']}' (ID: {portfolio_id})"
		)
	else:
		portfolio_name = "Main Portfolio"
		print(f"No portfolios found. Creating a new one named '{portfolio_name}'...")
		new_portfolio = repo.create_portfolio(portfolio_name, "Imported from TSV")
		portfolio_id = new_portfolio["id"]
		print(f"Created portfolio with ID: {portfolio_id}")

	parsed_transactions = []
	with open(tsv_path, "r", encoding="utf-8") as f:
		reader = csv.DictReader(f, delimiter="\t")
		for row in reader:
			tx = parse_row(row)
			if tx:
				parsed_transactions.append(tx)

	# Sort chronologically by date
	parsed_transactions.sort(key=lambda x: x["transaction_date"])

	print(f"\nParsed {len(parsed_transactions)} transactions. Recording to database...")
	recorded_count = 0
	for tx in parsed_transactions:
		try:
			repo.record_transaction(
				portfolio_id=portfolio_id,
				symbol=tx["symbol"],
				transaction_type=tx["transaction_type"],
				quantity=tx["quantity"],
				price_per_share=tx["price_per_share"],
				transaction_date=tx["transaction_date"],
				fees=tx["fees"],
				notes=tx["notes"],
				account=tx["account"],
				bank=tx["bank"],
				currency=tx["currency"],
				total_amount=tx["total_amount"],
				dividend_amount=tx["dividend_amount"],
				total_cost_cad=tx["total_cost_cad"],
			)
			recorded_count += 1
		except Exception as e:
			print(
				f"Failed to record transaction for {tx['symbol']} on {tx['transaction_date']}: {e}"
			)

	print(
		f"\nSuccessfully imported {recorded_count} of {len(parsed_transactions)} transactions."
	)


if __name__ == "__main__":
	main()
