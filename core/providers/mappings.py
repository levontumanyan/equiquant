"""
Provider-to-canonical metric key mappings.

Each entry maps a raw provider field name to a canonical key from core.metrics.
This is the explicit contract between a data provider and EquiQuant's scoring
engine. If a provider renames a field, only this file needs updating.

Pattern established by SECProvider._normalize — every provider maps to
canonical keys here rather than passing raw dicts directly into AssetData.metrics.
"""

from core.metrics import (
	AUDIT_RISK,
	BETA_3Y_AVG,
	BOARD_RISK,
	COMPENSATION_RISK,
	CURRENT_RATIO,
	DAYS_TO_COVER,
	DEBT_TO_EQUITY,
	DIVIDEND_YIELD,
	EBITDA_MARGIN,
	ENTERPRISE_TO_EBITDA,
	FORWARD_PE,
	INSIDER_OWNERSHIP,
	INSTITUTION_OWNERSHIP,
	OVERALL_RISK,
	PE_RATIO,
	PEG_RATIO,
	PRICE_TO_BOOK,
	PROFIT_MARGIN,
	RECOMMENDATION_MEAN,
	RETURN_ON_ASSETS,
	RETURN_ON_EQUITY,
	REVENUE_GROWTH,
	SHAREHOLDER_RIGHTS_RISK,
	SHORT_PERCENT_OF_FLOAT,
	TRAILING_PE,
)

# Maps raw OpenBB model_dump() field names → canonical metric keys.
# Sourced from: YFinanceKeyMetricsData, YFinanceShareStatisticsData,
#               YFinancePriceTargetConsensusData, YFinanceEtfInfoData.
# OpenBB already normalises its output to snake_case via Pydantic, so most
# entries are identity-like — but the explicit mapping is the point: it
# declares exactly which provider fields feed into scoring and makes
# provider version upgrades visible rather than silent.
OPENBB_METRIC_MAP: dict = {
	# YFinanceKeyMetricsData
	"pe_ratio": PE_RATIO,
	"forward_pe": FORWARD_PE,
	"peg_ratio": PEG_RATIO,
	"price_to_book": PRICE_TO_BOOK,
	"return_on_equity": RETURN_ON_EQUITY,
	"return_on_assets": RETURN_ON_ASSETS,
	"profit_margin": PROFIT_MARGIN,
	"ebitda_margin": EBITDA_MARGIN,
	"revenue_growth": REVENUE_GROWTH,
	"debt_to_equity": DEBT_TO_EQUITY,
	"current_ratio": CURRENT_RATIO,
	"dividend_yield": DIVIDEND_YIELD,
	"enterprise_to_ebitda": ENTERPRISE_TO_EBITDA,
	"overall_risk": OVERALL_RISK,
	"audit_risk": AUDIT_RISK,
	"board_risk": BOARD_RISK,
	"compensation_risk": COMPENSATION_RISK,
	"shareholder_rights_risk": SHAREHOLDER_RIGHTS_RISK,
	# YFinanceShareStatisticsData
	"insider_ownership": INSIDER_OWNERSHIP,
	"institution_ownership": INSTITUTION_OWNERSHIP,
	"short_percent_of_float": SHORT_PERCENT_OF_FLOAT,
	"days_to_cover": DAYS_TO_COVER,
	# YFinancePriceTargetConsensusData
	"recommendation_mean": RECOMMENDATION_MEAN,
	# YFinanceEtfInfoData
	"trailing_pe": TRAILING_PE,
	"beta_3y_avg": BETA_3Y_AVG,
}
