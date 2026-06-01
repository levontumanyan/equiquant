"""
Canonical metric key constants for EquiQuant.

Single source of truth for all metric key names used in scoring, seeds,
and the database. Production code must import from here — no raw string
literals for metric keys anywhere in core/.

Provider mapping files (mappings.py) use these as target values so a rename
here propagates to every provider contract automatically.
"""

# ── Valuation ─────────────────────────────────────────────────────────────────
PE_RATIO = "pe_ratio"
FORWARD_PE = "forward_pe"
TRAILING_PE = "trailing_pe"
PEG_RATIO = "peg_ratio"
PRICE_TO_BOOK = "price_to_book"
ENTERPRISE_TO_EBITDA = "enterprise_to_ebitda"

# ── Profitability ─────────────────────────────────────────────────────────────
RETURN_ON_EQUITY = "return_on_equity"
RETURN_ON_ASSETS = "return_on_assets"
PROFIT_MARGIN = "profit_margin"
EBITDA_MARGIN = "ebitda_margin"

# ── Growth ────────────────────────────────────────────────────────────────────
REVENUE_GROWTH = "revenue_growth"

# ── Leverage / Liquidity ──────────────────────────────────────────────────────
DEBT_TO_EQUITY = "debt_to_equity"
CURRENT_RATIO = "current_ratio"

# ── Ownership ─────────────────────────────────────────────────────────────────
INSIDER_OWNERSHIP = "insider_ownership"
INSTITUTION_OWNERSHIP = "institution_ownership"

# ── Short Interest ────────────────────────────────────────────────────────────
SHORT_PERCENT_OF_FLOAT = "short_percent_of_float"
DAYS_TO_COVER = "days_to_cover"

# ── Dividends / Analyst ───────────────────────────────────────────────────────
DIVIDEND_YIELD = "dividend_yield"
PAYOUT_RATIO = "payout_ratio"
RECOMMENDATION_MEAN = "recommendation_mean"

# ── Governance Risk ───────────────────────────────────────────────────────────
OVERALL_RISK = "overall_risk"
AUDIT_RISK = "audit_risk"
BOARD_RISK = "board_risk"
COMPENSATION_RISK = "compensation_risk"
SHAREHOLDER_RIGHTS_RISK = "shareholder_rights_risk"

# ── Penalty metrics (derived, not direct provider fields) ─────────────────────
DEBT_TO_EQUITY_PENALTY = "debt_to_equity_penalty"
OVERALL_RISK_PENALTY = "overall_risk_penalty"

# ── ETF-specific ──────────────────────────────────────────────────────────────
BETA_3Y_AVG = "beta_3y_avg"

# ── Non-OpenBB sources ────────────────────────────────────────────────────────
NET_INCOME = "net_income"  # SEC provider (NetIncomeLoss XBRL tag)

# P/E family: negative value means the ratio is mathematically undefined
# (no earnings → no meaningful ratio). Industry convention is N/A.
PE_FAMILY: frozenset = frozenset({PE_RATIO, FORWARD_PE, TRAILING_PE})
