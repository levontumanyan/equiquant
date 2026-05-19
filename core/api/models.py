from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from core.schema import AssetType


class BenchmarkResponse(BaseModel):
	"""Response model for benchmark data."""

	metric: str
	name: str
	type: str
	weight: float
	asset_type: str
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


class AppSetting(BaseModel):
	"""Model for application settings."""

	key: str
	value: str
	category: str
	description: Optional[str] = None
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
	market_cap: Optional[float] = None
