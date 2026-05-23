import asyncio

from fastapi import APIRouter, HTTPException

from core.api.deps import repo
from core.api.models import PortfolioCreate, TransactionCreate
from core.logger import get_logger
from core.orchestrator import fetch_data as orchestrator_fetch_data
from core.orchestrator import run_bulk_analysis

logger = get_logger(__name__)

router = APIRouter(prefix="/api")


@router.get("/portfolios")
async def list_portfolios():
	"""Return all portfolios with transaction counts."""
	try:
		return repo.list_portfolios()
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolios", status_code=201)
async def create_portfolio(request: PortfolioCreate):
	"""Create a new portfolio."""
	try:
		return repo.create_portfolio(request.name, request.description)
	except ValueError as e:
		raise HTTPException(status_code=409, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolios/{portfolio_id}")
async def get_portfolio(portfolio_id: int):
	"""Return a portfolio with its summary stats."""
	try:
		portfolio = repo.get_portfolio(portfolio_id)
		if portfolio is None:
			raise HTTPException(
				status_code=404, detail=f"Portfolio {portfolio_id} not found"
			)
		return portfolio
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.delete("/portfolios/{portfolio_id}")
async def delete_portfolio(portfolio_id: int):
	"""Delete a portfolio and all its transactions."""
	try:
		result = repo.delete_portfolio(portfolio_id)
		if result == "not_found":
			raise HTTPException(
				status_code=404, detail=f"Portfolio {portfolio_id} not found"
			)
		return {"status": "ok"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolios/{portfolio_id}/holdings")
async def get_holdings(portfolio_id: int):
	"""Return current aggregated holdings for a portfolio, enriched with asset metadata."""
	try:
		portfolio = repo.get_portfolio(portfolio_id)
		if portfolio is None:
			raise HTTPException(
				status_code=404, detail=f"Portfolio {portfolio_id} not found"
			)
		return repo.get_holdings(portfolio_id)
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolios/{portfolio_id}/transactions")
async def get_transactions(portfolio_id: int):
	"""Return the full transaction ledger for a portfolio."""
	try:
		portfolio = repo.get_portfolio(portfolio_id)
		if portfolio is None:
			raise HTTPException(
				status_code=404, detail=f"Portfolio {portfolio_id} not found"
			)
		return repo.get_transactions(portfolio_id)
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolios/{portfolio_id}/refresh-scores")
async def refresh_portfolio_scores(portfolio_id: int, profile: str = "balanced"):
	"""Fetch fresh data (if cache expired) and re-score all holdings.

	Follows the exact same path as the Analysis tab: cache check → optional
	OpenBB fetch → run_bulk_analysis → writes to analysis_snapshots.
	Returns the updated holdings with fresh scores.
	"""
	try:
		portfolio = repo.get_portfolio(portfolio_id)
		if portfolio is None:
			raise HTTPException(
				status_code=404, detail=f"Portfolio {portfolio_id} not found"
			)

		holdings = repo.get_holdings(portfolio_id)
		if not holdings:
			return {"refreshed": 0, "holdings": []}

		symbols = [h["symbol"] for h in holdings]

		# Mirror _split_tickers from analysis router
		missing = [s for s in symbols if not repo.should_use_db_cache(s)]
		if missing:
			async for _ in orchestrator_fetch_data(missing, repo=repo):
				pass

		results = run_bulk_analysis(
			tickers=symbols,
			profile=profile,
			repo=repo,
		)
		await asyncio.to_thread(repo.bulk_save_analyses, results, profile=profile)

		updated_holdings = repo.get_holdings(portfolio_id)
		return {"refreshed": len(results), "holdings": updated_holdings}
	except HTTPException:
		raise
	except Exception as e:
		logger.exception("Portfolio score refresh failed for %d", portfolio_id)
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolios/{portfolio_id}/transactions", status_code=201)
async def record_transaction(portfolio_id: int, request: TransactionCreate):
	"""Record a new transaction and update the holdings cache."""
	try:
		portfolio = repo.get_portfolio(portfolio_id)
		if portfolio is None:
			raise HTTPException(
				status_code=404, detail=f"Portfolio {portfolio_id} not found"
			)
		return repo.record_transaction(
			portfolio_id=portfolio_id,
			symbol=request.symbol,
			transaction_type=request.transaction_type,
			quantity=request.quantity,
			price_per_share=request.price_per_share,
			transaction_date=request.transaction_date,
			fees=request.fees,
			notes=request.notes,
			account=request.account,
			bank=request.bank,
			currency=request.currency,
			total_amount=request.total_amount,
			dividend_amount=request.dividend_amount,
			total_cost_cad=request.total_cost_cad,
		)
	except ValueError as e:
		raise HTTPException(status_code=422, detail=str(e))
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
