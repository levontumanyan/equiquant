from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from core.schema import AssetType


class BenchmarkResponse(BaseModel):
	"""Response model for benchmark data."""

	metric: str
	name: str
	type: str
	weight: float
	asset_type: str
	is_penalty: bool = False
	unit: Optional[str] = None
	best: Optional[float] = None
	worst: Optional[float] = None
	target: Optional[float] = None
	target_min: Optional[float] = None
	target_max: Optional[float] = None
	width: Optional[float] = None
	threshold: Optional[float] = None


class FetchRequest(BaseModel):
	"""Request model for data fetching."""

	tickers: List[str]
	provider: str = "openbb"


class AnalysisRequest(BaseModel):
	"""Request model for analysis."""

	tickers: List[str]
	profile: str = "balanced"
	benchmark_version: str = "1.0.0"
	context: Literal["global", "sector", "batch"] = "global"
	force_refresh: bool = False


class ExportRequest(BaseModel):
	"""Request model for data export."""

	results: List[Dict[str, Any]]
	format: str  # "csv" or "txt"
	profile: str = "balanced"
	tickers: List[str] = []
	index_name: Optional[str] = None


class GroupRequest(BaseModel):
	"""Request model for creating or updating a stock group."""

	name: str
	tickers: List[str]
	description: Optional[str] = None


class ProfileRequest(BaseModel):
	"""Request model for creating or updating an investor profile."""

	name: str
	weights: dict
	ranges: dict
	formulas: dict
	penalties: Dict[str, bool] = Field(default_factory=dict)


class AppSetting(BaseModel):
	"""Model for application settings."""

	key: str
	value: str
	category: str
	description: Optional[str] = None
	is_secret: bool = False
	last_updated: str


class SettingUpdate(BaseModel):
	"""Request model for updating an application setting."""

	value: str


class MetricResult(BaseModel):
	"""Result model for individual metrics."""

	metric: str
	name: str
	value: Any
	raw_value: Optional[float] = None
	score: float
	weight: float
	status: str
	is_penalty: bool = False
	source: Optional[str] = None


class AssetAnalysis(BaseModel):
	"""Full analysis result for a single asset."""

	symbol: str
	name: str
	asset_type: AssetType
	sector: Optional[str] = None
	industry: Optional[str] = None
	score: float
	results: List[MetricResult]
	raw_metrics: Optional[Dict[str, Any]] = None
	sources: Optional[Dict[str, str]] = None
	market_cap: Optional[float] = None


class PortfolioCreate(BaseModel):
	"""Request model for creating a portfolio."""

	name: str
	description: Optional[str] = None

	@field_validator("name")
	@classmethod
	def name_not_blank(cls, v: str) -> str:
		"""Reject empty or whitespace-only names."""
		stripped = v.strip()
		if not stripped:
			raise ValueError("Portfolio name cannot be blank")
		if len(stripped) > 100:
			raise ValueError("Portfolio name must be 100 characters or fewer")
		return stripped


class PortfolioResponse(BaseModel):
	"""Response model for a portfolio."""

	id: int
	name: str
	description: Optional[str] = None
	created_at: str
	updated_at: str
	transaction_count: Optional[int] = None


class TransactionCreate(BaseModel):
	"""Request model for recording a transaction."""

	symbol: str
	transaction_type: Literal["BUY", "SELL", "DIVIDEND"]
	quantity: float
	price_per_share: float
	transaction_date: str
	fees: float = 0.0
	notes: Optional[str] = None
	account: Optional[str] = None
	bank: Optional[str] = None
	currency: str = "USD"
	total_amount: Optional[float] = None
	dividend_amount: Optional[float] = None
	total_cost_cad: Optional[float] = None

	@field_validator("symbol")
	@classmethod
	def normalise_symbol(cls, v: str) -> str:
		"""Normalise ticker to uppercase."""
		return v.strip().upper()

	@field_validator("quantity", "price_per_share")
	@classmethod
	def positive_value(cls, v: float) -> float:
		"""Reject non-positive quantities and prices."""
		if v <= 0:
			raise ValueError("Must be greater than zero")
		return v

	@field_validator("fees")
	@classmethod
	def non_negative_fees(cls, v: float) -> float:
		"""Reject negative fees."""
		if v < 0:
			raise ValueError("Fees cannot be negative")
		return v


class TransactionResponse(BaseModel):
	"""Response model for a recorded transaction."""

	id: int
	portfolio_id: int
	account_id: Optional[int] = None
	account_name: Optional[str] = None
	bank_name: Optional[str] = None
	symbol: str
	transaction_type: str
	quantity: float
	price_per_share: float
	transaction_date: str
	fees: float
	currency: str
	total_amount: Optional[float] = None
	dividend_amount: Optional[float] = None
	total_cost_cad: Optional[float] = None
	notes: Optional[str] = None
	created_at: str


class HoldingResponse(BaseModel):
	"""Response model for a single portfolio holding."""

	symbol: str
	total_shares: float
	average_cost: float
	last_updated: str
	name: Optional[str] = None
	sector: Optional[str] = None
	asset_type: Optional[str] = None
	latest_score: Optional[float] = None
	account_name: Optional[str] = None
	bank_name: Optional[str] = None
	currency: str = "USD"
