import { useState, useEffect, useCallback, useRef, useMemo, type FormEvent } from 'react'
import { Maximize2, Minimize2 } from 'lucide-react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { PieChart, Pie, Cell, Tooltip } from 'recharts'
import { API_BASE_URL } from '../config'
import type { AssetAnalysis } from '../types'
import RawMetricsDrawer from './RawMetricsDrawer'
import ScoreWaterfallModal from './ScoreWaterfallModal'
import './PortfolioDashboard.css'

// ── Types ──────────────────────────────────────────────────────────────────

interface Portfolio {
	id: number
	name: string
	description: string | null
	created_at: string
	updated_at: string
	transaction_count: number
	total_fees: number
}

interface Holding {
	symbol: string
	total_shares: number
	average_cost: number
	cost_basis: number
	current_price: number | null
	market_value: number | null
	unrealized_pnl: number | null
	unrealized_pnl_pct: number | null
	last_updated: string
	name: string | null
	sector: string | null
	asset_type: string | null
	latest_score: number | null
	account_name: string | null
	bank_name: string | null
	currency: string
}

interface Transaction {
	id: number
	portfolio_id: number
	account_id: number | null
	account_name: string | null
	bank_name: string | null
	symbol: string
	transaction_type: 'BUY' | 'SELL' | 'DIVIDEND'
	quantity: number
	price_per_share: number
	transaction_date: string
	fees: number
	currency: string
	total_amount: number | null
	dividend_amount: number | null
	total_cost_cad: number | null
	notes: string | null
	created_at: string
}

type ActiveView = 'holdings' | 'accounts' | 'transactions'

// ── Helpers ────────────────────────────────────────────────────────────────

function scoreColor(score: number | null): string {
	if (score === null) return '#888'
	if (score >= 70) return '#4caf50'
	if (score >= 45) return '#ff9800'
	return '#f44336'
}

function fmtDate(iso: string): string {
	return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function fmtMoney(n: number): string {
	return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtCurrencyMoney(n: number, currency: string): string {
	const prefix = currency === 'CAD' ? 'C$' : '$'
	return `${prefix}${fmtMoney(n)}`
}

function convertToDisplay(value: number, fromCurrency: string, displayCurrency: string, usdcadRate: number): number {
	if (fromCurrency === displayCurrency) return value
	if (fromCurrency === 'USD' && displayCurrency === 'CAD') return value * usdcadRate
	if (fromCurrency === 'CAD' && displayCurrency === 'USD') return value / usdcadRate
	return value
}


// ── Confirm-delete modal ───────────────────────────────────────────────────

function ConfirmDeleteModal({ portfolio, onClose, onConfirm, loading }: {
	portfolio: Portfolio
	onClose: () => void
	onConfirm: () => void
	loading: boolean
}) {
	return (
		<div className="pd-modal-overlay" onClick={onClose}>
			<div className="pd-modal pd-modal-sm" onClick={e => e.stopPropagation()}>
				<div className="pd-confirm-icon">⚠</div>
				<h3 className="pd-confirm-title">Delete Portfolio</h3>
				<p className="pd-confirm-body">
					<strong>{portfolio.name}</strong> has{' '}
					<strong>{portfolio.transaction_count} {portfolio.transaction_count === 1 ? 'trade' : 'trades'}</strong>.
					Deleting it will permanently remove all holdings and transaction history.
					This cannot be undone.
				</p>
				<div className="pd-modal-actions">
					<button className="pd-btn pd-btn-ghost" onClick={onClose} disabled={loading}>Cancel</button>
					<button className="pd-btn pd-btn-danger" onClick={onConfirm} disabled={loading}>
						{loading ? 'Deleting…' : 'Delete Portfolio'}
					</button>
				</div>
			</div>
		</div>
	)
}

// ── Create-portfolio modal ─────────────────────────────────────────────────

function CreatePortfolioModal({ onClose, onCreated }: { onClose: () => void; onCreated: (p: Portfolio) => void }) {
	const [name, setName] = useState('')
	const [description, setDescription] = useState('')
	const [error, setError] = useState<string | null>(null)
	const [loading, setLoading] = useState(false)

	async function handleSubmit(e: FormEvent) {
		e.preventDefault()
		if (!name.trim()) { setError('Name is required'); return }
		setLoading(true)
		setError(null)
		try {
			const res = await fetch(`${API_BASE_URL}/api/portfolios`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: name.trim(), description: description.trim() || null }),
			})
			if (!res.ok) {
				const data = await res.json()
				throw new Error(data.detail || 'Failed to create portfolio')
			}
			const created: Portfolio = await res.json()
			onCreated(created)
		} catch (err: any) {
			setError(err.message)
		} finally {
			setLoading(false)
		}
	}

	return (
		<div className="pd-modal-overlay" onClick={onClose}>
			<div className="pd-modal" onClick={e => e.stopPropagation()}>
				<div className="pd-modal-header">
					<h3>New Portfolio</h3>
					<button className="pd-icon-btn" onClick={onClose}>✕</button>
				</div>
				<form onSubmit={handleSubmit}>
					<label>
						Name
						<input
							autoFocus
							value={name}
							onChange={e => setName(e.target.value)}
							placeholder="My Portfolio"
						/>
					</label>
					<label>
						Description <span className="pd-optional">(optional)</span>
						<input
							value={description}
							onChange={e => setDescription(e.target.value)}
							placeholder="Short description…"
						/>
					</label>
					{error && <p className="pd-error">{error}</p>}
					<div className="pd-modal-actions">
						<button type="button" className="pd-btn pd-btn-ghost" onClick={onClose}>Cancel</button>
						<button type="submit" className="pd-btn pd-btn-primary" disabled={loading}>
							{loading ? 'Creating…' : 'Create'}
						</button>
					</div>
				</form>
			</div>
		</div>
	)
}

// ── Add-transaction modal ──────────────────────────────────────────────────

function AddTransactionModal({
	portfolioId,
	onClose,
	onAdded,
}: {
	portfolioId: number
	onClose: () => void
	onAdded: (tx: Transaction) => void
}) {
	const [symbol, setSymbol] = useState('')
	const [type, setType] = useState<'BUY' | 'SELL' | 'DIVIDEND'>('BUY')
	const [quantity, setQuantity] = useState('')
	const [price, setPrice] = useState('')
	const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
	const [fees, setFees] = useState('0')
	const [account, setAccount] = useState('TFSA')
	const [bank, setBank] = useState('RBC')
	const [currency, setCurrency] = useState('CAD')
	const [dividendAmount, setDividendAmount] = useState('')
	const [totalCostCad, setTotalCostCad] = useState('')
	const [notes, setNotes] = useState('')
	const [error, setError] = useState<string | null>(null)
	const [loading, setLoading] = useState(false)

	async function handleSubmit(e: FormEvent) {
		e.preventDefault()
		if (type === 'DIVIDEND') {
			if (!symbol.trim() || !dividendAmount) { setError('Symbol and Dividend Amount are required'); return }
		} else {
			if (!symbol.trim() || !quantity || !price) { setError('Symbol, quantity, and price are required'); return }
		}
		setLoading(true)
		setError(null)
		try {
			const res = await fetch(`${API_BASE_URL}/api/portfolios/${portfolioId}/transactions`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					symbol: symbol.trim().toUpperCase(),
					transaction_type: type,
					quantity: type === 'DIVIDEND' ? 1.0 : parseFloat(quantity),
					price_per_share: type === 'DIVIDEND' ? parseFloat(dividendAmount) : parseFloat(price),
					transaction_date: date,
					fees: parseFloat(fees) || 0,
					account: account.trim() || null,
					bank: bank.trim() || null,
					currency: currency,
					dividend_amount: type === 'DIVIDEND' ? parseFloat(dividendAmount) : null,
					total_cost_cad: parseFloat(totalCostCad) || null,
					notes: notes.trim() || null,
				}),
			})
			if (!res.ok) {
				const data = await res.json()
				throw new Error(data.detail || 'Failed to record transaction')
			}
			const tx: Transaction = await res.json()
			onAdded(tx)
		} catch (err: any) {
			setError(err.message)
		} finally {
			setLoading(false)
		}
	}

	return (
		<div className="pd-modal-overlay" onClick={onClose}>
			<div className="pd-modal" onClick={e => e.stopPropagation()}>
				<div className="pd-modal-header">
					<h3>Add Transaction</h3>
					<button className="pd-icon-btn" onClick={onClose}>✕</button>
				</div>
				<form onSubmit={handleSubmit}>
					<div className="pd-form-row">
						<label>
							Symbol
							<input
								autoFocus
								value={symbol}
								onChange={e => setSymbol(e.target.value.toUpperCase())}
								placeholder="AAPL"
							/>
						</label>
						<label>
							Type
							<select value={type} onChange={e => setType(e.target.value as any)}>
								<option value="BUY">BUY</option>
								<option value="SELL">SELL</option>
								<option value="DIVIDEND">DIVIDEND</option>
							</select>
						</label>
					</div>
					<div className="pd-form-row">
						<label>
							Account
							<input value={account} onChange={e => setAccount(e.target.value)} placeholder="TFSA, RRSP, FHSA…" />
						</label>
						<label>
							Bank
							<input value={bank} onChange={e => setBank(e.target.value)} placeholder="RBC, TD, Schwab…" />
						</label>
					</div>
					<div className="pd-form-row">
						<label>
							Currency
							<select value={currency} onChange={e => setCurrency(e.target.value)}>
								<option value="CAD">CAD</option>
								<option value="USD">USD</option>
							</select>
						</label>
						<label>
							Date
							<input type="date" value={date} onChange={e => setDate(e.target.value)} />
						</label>
					</div>
					{type !== 'DIVIDEND' ? (
						<div className="pd-form-row">
							<label>
								Quantity
								<input type="number" min="0.0001" step="any" value={quantity} onChange={e => setQuantity(e.target.value)} placeholder="100" />
							</label>
							<label>
								Price / Share
								<input type="number" min="0.0001" step="any" value={price} onChange={e => setPrice(e.target.value)} placeholder="150.00" />
							</label>
						</div>
					) : (
						<div className="pd-form-row">
							<label>
								Dividend Amount
								<input type="number" min="0.0001" step="any" value={dividendAmount} onChange={e => setDividendAmount(e.target.value)} placeholder="11.50" />
							</label>
						</div>
					)}
					<div className="pd-form-row">
						<label>
							Fees
							<input type="number" min="0" step="any" value={fees} onChange={e => setFees(e.target.value)} placeholder="0.00" />
						</label>
						<label>
							Total Cost CAD <span className="pd-optional">(optional)</span>
							<input type="number" min="0" step="any" value={totalCostCad} onChange={e => setTotalCostCad(e.target.value)} placeholder="0.00" />
						</label>
					</div>
					<label>
						Notes <span className="pd-optional">(optional)</span>
						<input value={notes} onChange={e => setNotes(e.target.value)} placeholder="Optional note…" />
					</label>
					{error && <p className="pd-error">{error}</p>}
					<div className="pd-modal-actions">
						<button type="button" className="pd-btn pd-btn-ghost" onClick={onClose}>Cancel</button>
						<button type="submit" className="pd-btn pd-btn-primary" disabled={loading}>
							{loading ? 'Saving…' : 'Save'}
						</button>
					</div>
				</form>
			</div>
		</div>
	)
}

// ── Palette for pie slices ─────────────────────────────────────────────────

const PIE_COLORS = [
	'#9ea0ff', '#4caf50', '#ff9800', '#f06292', '#4dd0e1',
	'#aed581', '#ffb74d', '#ba68c8', '#4db6ac', '#e57373',
	'#64b5f6', '#ffd54f', '#a1887f', '#90a4ae', '#81c784',
]

// ── Holdings pie chart ─────────────────────────────────────────────────────

function HoldingsPieChart({ rows, displayCurrency }: {
	rows: { symbol: string; value: number }[]
	displayCurrency: string
}) {
	const [active, setActive] = useState<string | null>(null)
	const prefix = displayCurrency === 'CAD' ? 'C$' : '$'

	return (
		<div className="pd-pie-wrap">
			<div style={{ width: 220, height: 220, flexShrink: 0 }}>
				<PieChart width={220} height={220}>
					<Pie
						data={rows}
						dataKey="value"
						nameKey="symbol"
						cx="50%"
						cy="50%"
						innerRadius={60}
						outerRadius={100}
						strokeWidth={2}
						stroke="#141414"
						onMouseEnter={(_: unknown, idx: number) => setActive(rows[idx].symbol)}
						onMouseLeave={() => setActive(null)}
					>
						{rows.map((r, i) => (
							<Cell
								key={r.symbol}
								fill={PIE_COLORS[i % PIE_COLORS.length]}
								opacity={active === null || active === r.symbol ? 1 : 0.35}
							/>
						))}
					</Pie>
					<Tooltip
						content={({ active, payload }) => {
							if (!active || !payload?.length) return null
							const { name, value } = payload[0]
							return (
								<div className="pd-pie-tooltip">
									<span className="pd-pie-tooltip-sym">{name}</span>
									<span>{prefix}{fmtMoney(value as number)}</span>
								</div>
							)
						}}
					/>
				</PieChart>
			</div>
			<div className="pd-pie-legend">
				{rows.map((r, i) => {
					const total = rows.reduce((s, x) => s + x.value, 0)
					const pct = total > 0 ? (r.value / total) * 100 : 0
					return (
						<div
							key={r.symbol}
							className={`pd-pie-legend-item${active === r.symbol ? ' pd-pie-legend-active' : ''}`}
							onMouseEnter={() => setActive(r.symbol)}
							onMouseLeave={() => setActive(null)}
						>
							<span className="pd-pie-dot" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
							<span className="pd-pie-sym">{r.symbol}</span>
							<span className="pd-pie-pct pd-muted">{pct.toFixed(1)}%</span>
						</div>
					)
				})}
			</div>
		</div>
	)
}

// ── Holdings table (collapsed by symbol) ──────────────────────────────────

function HoldingsTable({ holdings, displayCurrency, usdcadRate, fullscreen, onTickerClick, onScoreClick }: {
	holdings: Holding[]
	displayCurrency: 'USD' | 'CAD'
	usdcadRate: number | null
	fullscreen: boolean
	onTickerClick: (h: Holding) => void
	onScoreClick: (symbol: string) => void
}) {
	if (holdings.length === 0) {
		return (
			<div className="pd-empty">
				<p>No holdings yet. Use <strong>+ Transaction</strong> to record your first trade.</p>
			</div>
		)
	}

	const conv = (v: number, fromCurrency: string) =>
		usdcadRate !== null ? convertToDisplay(v, fromCurrency, displayCurrency, usdcadRate) : v
	const fmt = (v: number) => fmtCurrencyMoney(v, displayCurrency)

	// Collapse rows by symbol — aggregate cost/value in displayCurrency
	type AggRow = {
		symbol: string; name: string | null; sector: string | null
		asset_type: string | null; latest_score: number | null
		totalShares: number; costBasis: number; marketValue: number | null
		pnl: number | null; pnlPct: number | null
		currentPrice: number | null
		accounts: string[]; representative: Holding
	}

	const rows = useMemo<AggRow[]>(() => {
		const symbolMap = new Map<string, Holding[]>()
		for (const h of holdings) {
			const hs = symbolMap.get(h.symbol) ?? []
			hs.push(h)
			symbolMap.set(h.symbol, hs)
		}
		return [...symbolMap.entries()].map(([symbol, hs]) => {
			const totalShares = hs.reduce((s, h) => s + h.total_shares, 0)
			const costBasis = hs.reduce((s, h) => s + conv(h.cost_basis, h.currency), 0)
			const hasPrice = hs.some(h => h.market_value !== null)
			const marketValue = hasPrice ? hs.reduce((s, h) => s + conv(h.market_value ?? h.cost_basis, h.currency), 0) : null
			const pnl = marketValue !== null ? marketValue - costBasis : null
			const pnlPct = pnl !== null && costBasis > 0 ? (pnl / costBasis) * 100 : null
			const first = hs[0]
			const priceRow = hs.find(h => h.current_price !== null)
			const currentPrice = priceRow ? conv(priceRow.current_price!, priceRow.currency) : null
			const accounts = [...new Set(hs.map(h => h.account_name).filter(Boolean))] as string[]
			return { symbol, name: first.name, sector: first.sector, asset_type: first.asset_type,
				latest_score: first.latest_score, totalShares, costBasis, marketValue,
				pnl, pnlPct, currentPrice, accounts, representative: first }
		})
	}, [holdings, displayCurrency, usdcadRate])

	const totalMV = useMemo(() => rows.reduce((s, r) => s + (r.marketValue ?? r.costBasis), 0), [rows])

	const pieData = useMemo(() =>
		rows.map(r => ({ symbol: r.symbol, value: r.marketValue ?? r.costBasis }))
			.sort((a, b) => b.value - a.value),
		[rows]
	)

	return (
		<>
		{!fullscreen && usdcadRate !== null && pieData.length > 0 && (
			<HoldingsPieChart rows={pieData} displayCurrency={displayCurrency} />
		)}
		<div className="pd-table-wrap">
			<table className="pd-table">
				<thead>
					<tr>
						<th>Symbol</th>
						<th>Name</th>
						<th>Type</th>
						<th>Accounts</th>
						<th className="pd-right">Shares</th>
						<th className="pd-right">Cost Basis</th>
						<th className="pd-right">Price</th>
						<th className="pd-right">Market Value</th>
						<th className="pd-right">Unrealized P&L</th>
						<th className="pd-right">Weight</th>
						<th className="pd-right">Score</th>
					</tr>
				</thead>
				<tbody>
					{rows.map(r => {
						const pnlColor = r.pnl === null ? '#888' : r.pnl >= 0 ? '#4caf50' : '#f44336'
						const weightPct = totalMV > 0 ? ((r.marketValue ?? r.costBasis) / totalMV) * 100 : 0
						return (
							<tr key={r.symbol}>
								<td className="pd-symbol">
									<button className="pd-ticker-link" onClick={() => onTickerClick(r.representative)}>{r.symbol}</button>
								</td>
								<td>{r.name ?? '—'}</td>
								<td>
									{r.asset_type ? (
										<span className={`pd-badge pd-badge-${r.asset_type.toLowerCase()}`}>
											{r.asset_type === 'STOCK' ? 'Stock' : r.asset_type}
										</span>
									) : <span className="pd-muted">—</span>}
								</td>
								<td>
									{r.accounts.length === 0
										? <span className="pd-muted">—</span>
										: r.accounts.map(a => <span key={a} className="pd-badge pd-badge-account" style={{ marginRight: '3px' }}>{a}</span>)}
								</td>
								<td className="pd-right">{r.totalShares.toLocaleString(undefined, { maximumFractionDigits: 4 })}</td>
								<td className="pd-right">{fmt(r.costBasis)}</td>
								<td className="pd-right">{r.currentPrice !== null ? fmt(r.currentPrice) : <span className="pd-muted">—</span>}</td>
								<td className="pd-right">{r.marketValue !== null ? fmt(r.marketValue) : <span className="pd-muted">—</span>}</td>
								<td className="pd-right" style={{ color: pnlColor }}>
									{r.pnl !== null
										? `${r.pnl >= 0 ? '+' : ''}${fmt(r.pnl)}${r.pnlPct != null ? ` (${r.pnlPct.toFixed(1)}%)` : ''}`
										: <span className="pd-muted">—</span>}
								</td>
								<td className="pd-right pd-muted">{weightPct.toFixed(1)}%</td>
								<td className="pd-right">
									{r.latest_score !== null
										? <button className="pd-score-chip" style={{ color: scoreColor(r.latest_score) }} onClick={() => onScoreClick(r.symbol)}>{r.latest_score.toFixed(1)}</button>
										: <span className="pd-score-chip pd-score-na">—</span>}
								</td>
							</tr>
						)
					})}
				</tbody>
			</table>
		</div>
		</>
	)
}

// ── Accounts table (grouped by account + currency) ─────────────────────────

function AccountsTable({ holdings, onTickerClick, onScoreClick }: {
	holdings: Holding[]
	onTickerClick: (h: Holding) => void
	onScoreClick: (symbol: string) => void
}) {
	if (holdings.length === 0) {
		return (
			<div className="pd-empty">
				<p>No holdings yet. Use <strong>+ Transaction</strong> to record your first trade.</p>
			</div>
		)
	}

	// Group by account+currency — values stay in native currency per group
	type GroupKey = string
	const groupMap = new Map<GroupKey, Holding[]>()
	for (const h of holdings) {
		const key = `${h.account_name ?? '—'}||${h.bank_name ?? '—'}||${h.currency}`
		const rows = groupMap.get(key) ?? []
		rows.push(h)
		groupMap.set(key, rows)
	}

	// Sort groups: by account name then currency
	const groups = [...groupMap.entries()].sort(([a], [b]) => a.localeCompare(b))

	return (
		<div className="pd-accounts-wrap">
			{groups.map(([key, hs]) => {
				const [accountName, bankName, currency] = key.split('||')
				const totalCost = hs.reduce((s, h) => s + h.cost_basis, 0)
				const hasPrice = hs.some(h => h.market_value !== null)
				const totalMV = hasPrice ? hs.reduce((s, h) => s + (h.market_value ?? h.cost_basis), 0) : null
				const totalPnl = totalMV !== null ? totalMV - totalCost : null
				const totalPnlPct = totalPnl !== null && totalCost > 0 ? (totalPnl / totalCost) * 100 : null
				const nat = (v: number) => fmtCurrencyMoney(v, currency)
				const pnlColor = totalPnl === null ? '#888' : totalPnl >= 0 ? '#4caf50' : '#f44336'

				return (
					<div key={key} className="pd-account-group">
						<div className="pd-account-group-header">
							<div className="pd-account-group-title">
								<span className="pd-badge pd-badge-account">{accountName}</span>
								{bankName !== '—' && <span className="pd-muted" style={{ fontSize: '0.78rem' }}>{bankName}</span>}
								<span className={`pd-badge pd-badge-currency pd-badge-currency-${currency.toLowerCase()}`}>{currency}</span>
							</div>
							<div className="pd-account-group-totals">
								<span className="pd-account-stat"><span className="pd-muted">Cost</span> {nat(totalCost)}</span>
								<span className="pd-account-stat"><span className="pd-muted">Value</span> {totalMV !== null ? nat(totalMV) : '—'}</span>
								<span className="pd-account-stat" style={{ color: pnlColor }}>
									{totalPnl !== null ? `${totalPnl >= 0 ? '+' : ''}${nat(totalPnl)}${totalPnlPct != null ? ` (${totalPnlPct.toFixed(1)}%)` : ''}` : '—'}
								</span>
							</div>
						</div>
						<div className="pd-table-wrap">
						<table className="pd-table">
							<thead>
								<tr>
									<th>Symbol</th>
									<th>Name</th>
									<th className="pd-right">Shares</th>
									<th className="pd-right">Avg Cost</th>
									<th className="pd-right">Cost Basis</th>
									<th className="pd-right">Price</th>
									<th className="pd-right">Market Value</th>
									<th className="pd-right">P&L</th>
									<th className="pd-right">Score</th>
								</tr>
							</thead>
							<tbody>
								{hs.map(h => {
									const pnl = h.unrealized_pnl
									const pColor = pnl === null ? '#888' : pnl >= 0 ? '#4caf50' : '#f44336'
									return (
										<tr key={`${h.symbol}-${h.currency}`}>
											<td className="pd-symbol">
												<button className="pd-ticker-link" onClick={() => onTickerClick(h)}>{h.symbol}</button>
											</td>
											<td>{h.name ?? '—'}</td>
											<td className="pd-right">{h.total_shares.toLocaleString(undefined, { maximumFractionDigits: 4 })}</td>
											<td className="pd-right">{nat(h.average_cost)}</td>
											<td className="pd-right">{nat(h.cost_basis)}</td>
											<td className="pd-right">{h.current_price !== null ? nat(h.current_price) : <span className="pd-muted">—</span>}</td>
											<td className="pd-right">{h.market_value !== null ? nat(h.market_value) : <span className="pd-muted">—</span>}</td>
											<td className="pd-right" style={{ color: pColor }}>
												{pnl !== null
													? `${pnl >= 0 ? '+' : ''}${nat(pnl)}${h.unrealized_pnl_pct != null ? ` (${h.unrealized_pnl_pct.toFixed(1)}%)` : ''}`
													: <span className="pd-muted">—</span>}
											</td>
											<td className="pd-right">
												{h.latest_score !== null
													? <button className="pd-score-chip" style={{ color: scoreColor(h.latest_score) }} onClick={() => onScoreClick(h.symbol)}>{h.latest_score.toFixed(1)}</button>
													: <span className="pd-score-chip pd-score-na">—</span>}
											</td>
										</tr>
									)
								})}
							</tbody>
						</table>
						</div>
					</div>
				)
			})}
		</div>
	)
}

// ── Transaction ledger ────────────────────────────────────────────────────

function TransactionLedger({ transactions }: { transactions: Transaction[] }) {
	if (transactions.length === 0) {
		return (
			<div className="pd-empty">
				<p>No transactions recorded. Use <strong>+ Transaction</strong> to add one.</p>
			</div>
		)
	}

	return (
		<div className="pd-table-wrap">
			<table className="pd-table">
				<thead>
					<tr>
						<th>Date</th>
						<th>Symbol</th>
						<th>Type</th>
						<th>Account</th>
						<th>Bank</th>
						<th className="pd-right">Qty</th>
						<th className="pd-right">Price</th>
						<th className="pd-right">Fees</th>
						<th className="pd-right">Total</th>
						<th className="pd-right">Total (CAD)</th>
						<th>Notes</th>
					</tr>
				</thead>
				<tbody>
					{transactions.map(tx => {
						const gross = tx.quantity * tx.price_per_share
						const total = tx.transaction_type === 'SELL'
							? gross - tx.fees
							: tx.transaction_type === 'DIVIDEND'
							? gross
							: gross + tx.fees
						const displayTotal = tx.total_amount !== null ? tx.total_amount : total
						return (
							<tr key={tx.id}>
								<td className="pd-muted">{fmtDate(tx.transaction_date)}</td>
								<td className="pd-symbol">{tx.symbol}</td>
								<td>
									<span className={`pd-badge pd-badge-${tx.transaction_type.toLowerCase()}`}>
										{tx.transaction_type}
									</span>
								</td>
								<td>
									<span className="pd-badge pd-badge-account">{tx.account_name ?? '—'}</span>
								</td>
								<td className="pd-muted">{tx.bank_name ?? '—'}</td>
								<td className="pd-right">
									{tx.transaction_type === 'DIVIDEND' ? '—' : tx.quantity.toLocaleString(undefined, { maximumFractionDigits: 4 })}
								</td>
								<td className="pd-right">
									{tx.transaction_type === 'DIVIDEND' && tx.dividend_amount !== null
										? fmtCurrencyMoney(tx.dividend_amount, tx.currency)
										: fmtCurrencyMoney(tx.price_per_share, tx.currency)}
								</td>
								<td className="pd-right">{tx.fees > 0 ? fmtCurrencyMoney(tx.fees, tx.currency) : '—'}</td>
								<td className="pd-right">{fmtCurrencyMoney(displayTotal, tx.currency)}</td>
								<td className="pd-right pd-muted">
									{tx.total_cost_cad !== null ? `C$${fmtMoney(tx.total_cost_cad)}` : '—'}
								</td>
								<td className="pd-muted">{tx.notes ?? '—'}</td>
							</tr>
						)
					})}
				</tbody>
			</table>
		</div>
	)
}

// ── Main component ─────────────────────────────────────────────────────────

export default function PortfolioDashboard() {
	const [portfolios, setPortfolios] = useState<Portfolio[]>([])
	const [activePortfolio, setActivePortfolio] = useState<Portfolio | null>(null)
	const [holdings, setHoldings] = useState<Holding[]>([])
	const [transactions, setTransactions] = useState<Transaction[]>([])
	const [activeView, setActiveView] = useState<ActiveView>('holdings')
	const [showCreateModal, setShowCreateModal] = useState(false)
	const [showTxModal, setShowTxModal] = useState(false)
	const [loadingPortfolios, setLoadingPortfolios] = useState(true)
	const [loadingDetail, setLoadingDetail] = useState(false)
	const [refreshing, setRefreshing] = useState(false)
	const [fullscreen, setFullscreen] = useState(false)
	const [pendingDelete, setPendingDelete] = useState<Portfolio | null>(null)
	const [deleting, setDeleting] = useState(false)
	const [error, setError] = useState<string | null>(null)
	const [displayCurrency, setDisplayCurrency] = useState<'USD' | 'CAD'>('CAD')
	const [usdcadRate, setUsdcadRate] = useState<number | null>(null)
	const [rawDrawerAsset, setRawDrawerAsset] = useState<AssetAnalysis | null>(null)
	const [waterfallAsset, setWaterfallAsset] = useState<AssetAnalysis | null>(null)
	const [loadingWaterfall, setLoadingWaterfall] = useState<string | null>(null)
	const waterfallAbortRef = useRef<AbortController | null>(null)

	// Fetch USD/CAD rate once on mount; cached for 24h server-side
	useEffect(() => {
		fetch(`${API_BASE_URL}/api/fx/rate?from=USD&to=CAD`)
			.then(r => r.ok ? r.json() : null)
			.then(data => { if (data?.rate) setUsdcadRate(data.rate) })
			.catch(() => {})
	}, [])

	// Fetch portfolios list — no dependency on activePortfolio to avoid stale closure
	const fetchPortfolios = useCallback(async () => {
		setLoadingPortfolios(true)
		try {
			const res = await fetch(`${API_BASE_URL}/api/portfolios`)
			if (!res.ok) throw new Error('Failed to load portfolios')
			const data: Portfolio[] = await res.json()
			setPortfolios(data)
			// Auto-select first only if nothing is selected yet
			setActivePortfolio(prev => prev ?? (data[0] ?? null))
		} catch (err: any) {
			setError(err.message)
		} finally {
			setLoadingPortfolios(false)
		}
	}, [])

	useEffect(() => { fetchPortfolios() }, [fetchPortfolios])

	// Fetch holdings + transactions when active portfolio changes
	useEffect(() => {
		if (!activePortfolio) { setHoldings([]); setTransactions([]); return }
		setLoadingDetail(true)
		Promise.all([
			fetch(`${API_BASE_URL}/api/portfolios/${activePortfolio.id}/holdings`).then(r => {
				if (!r.ok) throw new Error(`Holdings fetch failed: ${r.status}`)
				return r.json()
			}),
			fetch(`${API_BASE_URL}/api/portfolios/${activePortfolio.id}/transactions`).then(r => {
				if (!r.ok) throw new Error(`Transactions fetch failed: ${r.status}`)
				return r.json()
			}),
		]).then(([h, t]) => {
			setHoldings(Array.isArray(h) ? h : [])
			setTransactions(Array.isArray(t) ? t : [])
		}).catch(err => setError(err.message))
			.finally(() => setLoadingDetail(false))
	}, [activePortfolio])

	function handleDelete(portfolio: Portfolio) {
		setPendingDelete(portfolio)
	}

	async function confirmDelete() {
		if (!pendingDelete) return
		setDeleting(true)
		try {
			const res = await fetch(`${API_BASE_URL}/api/portfolios/${pendingDelete.id}`, { method: 'DELETE' })
			if (!res.ok) throw new Error('Failed to delete')
			const updated = portfolios.filter(p => p.id !== pendingDelete.id)
			setPortfolios(updated)
			if (activePortfolio?.id === pendingDelete.id) setActivePortfolio(updated[0] ?? null)
			setPendingDelete(null)
		} catch (err: any) {
			setError(err.message)
		} finally {
			setDeleting(false)
		}
	}

	function handlePortfolioCreated(p: Portfolio) {
		setPortfolios(prev => [...prev, p])
		setActivePortfolio(p)
		setShowCreateModal(false)
	}

	async function handleRefreshScores() {
		if (!activePortfolio || refreshing) return
		setRefreshing(true)
		setError(null)
		try {
			const res = await fetch(
				`${API_BASE_URL}/api/portfolios/${activePortfolio.id}/refresh-scores`,
				{ method: 'POST' }
			)
			if (!res.ok) throw new Error('Refresh failed')
			const data = await res.json()
			setHoldings(Array.isArray(data.holdings) ? data.holdings : [])
		} catch (err: any) {
			setError(err.message)
		} finally {
			setRefreshing(false)
		}
	}

	function handleTransactionAdded(tx: Transaction) {
		setTransactions(prev => [tx, ...prev])
		if (activePortfolio) {
			// Refresh holdings and portfolio stats (total_fees) together
			Promise.all([
				fetch(`${API_BASE_URL}/api/portfolios/${activePortfolio.id}/holdings`).then(r => r.json()),
				fetch(`${API_BASE_URL}/api/portfolios/${activePortfolio.id}`).then(r => r.json()),
			]).then(([h, p]) => {
				setHoldings(Array.isArray(h) ? h : [])
				setActivePortfolio(p)
			}).catch(() => {})
		}
		setShowTxModal(false)
		setActiveView('holdings')
	}

	function openRawDrawer(h: { symbol: string; name: string | null; sector: string | null; latest_score: number | null }) {
		setRawDrawerAsset({ symbol: h.symbol, name: h.name ?? h.symbol, sector: h.sector, industry: null, score: h.latest_score ?? 0, results: [] })
	}

	function openWaterfall(symbol: string) {
		waterfallAbortRef.current?.abort()
		const controller = new AbortController()
		waterfallAbortRef.current = controller
		setLoadingWaterfall(symbol)
		setWaterfallAsset(null)

		fetchEventSource(`${API_BASE_URL}/api/analyze/stream`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ tickers: [symbol], profile: 'balanced', context: 'global' }),
			signal: controller.signal,
			openWhenHidden: true,
			onmessage(ev) {
				if (ev.event === 'result') {
					setWaterfallAsset(JSON.parse(ev.data))
					setLoadingWaterfall(null)
					controller.abort()
				} else if (ev.event === 'error') {
					setLoadingWaterfall(null)
					controller.abort()
				}
			},
			onerror(err) {
				if (!controller.signal.aborted) setLoadingWaterfall(null)
				throw err
			},
			onclose() { setLoadingWaterfall(null) },
		})
	}

	// Summary stats — all converted to displayCurrency before summing
	const toDisplayStat = (v: number, fromCurrency: string) =>
		usdcadRate !== null ? convertToDisplay(v, fromCurrency, displayCurrency, usdcadRate) : v

	const totalCost = holdings.reduce((sum, h) => sum + toDisplayStat(h.cost_basis, h.currency), 0)
	const totalMarketValue = holdings.every(h => h.market_value === null)
		? null
		: holdings.reduce((sum, h) => sum + toDisplayStat(h.market_value ?? h.cost_basis, h.currency), 0)
	const totalPnl = totalMarketValue !== null ? totalMarketValue - totalCost : null
	const totalPnlPct = totalPnl !== null && totalCost > 0 ? (totalPnl / totalCost) * 100 : null
	const displayPrefix = displayCurrency === 'CAD' ? 'C$' : '$'
	const fxNote = usdcadRate !== null
		? `Converted at 1 USD = C$${usdcadRate.toFixed(4)}`
		: 'FX rate unavailable — showing native totals'
	const scoredHoldings = holdings.filter(h => h.latest_score !== null)
	const avgScore = scoredHoldings.length > 0
		? scoredHoldings.reduce((sum, h) => sum + (h.latest_score ?? 0), 0) / scoredHoldings.length
		: null

	return (
		<div className="pd-root">
			{/* Sidebar */}
			<aside className="pd-sidebar">
				<div className="pd-sidebar-header">
					<span className="pd-sidebar-title">Portfolios</span>
					<button className="pd-btn pd-btn-primary pd-btn-sm" onClick={() => setShowCreateModal(true)}>+ New</button>
				</div>

				{loadingPortfolios ? (
					<p className="pd-sidebar-empty">Loading…</p>
				) : portfolios.length === 0 ? (
					<p className="pd-sidebar-empty">No portfolios yet.</p>
				) : (
					<ul className="pd-portfolio-list">
						{portfolios.map(p => (
							<li
								key={p.id}
								className={`pd-portfolio-item${activePortfolio?.id === p.id ? ' pd-active' : ''}`}
								onClick={() => setActivePortfolio(p)}
							>
								<div className="pd-portfolio-item-name">{p.name}</div>
								<div className="pd-portfolio-item-meta">{p.transaction_count} {p.transaction_count === 1 ? 'trade' : 'trades'}</div>
								<button
									className="pd-delete-btn"
									onClick={e => { e.stopPropagation(); handleDelete(p) }}
									title="Delete portfolio"
								>✕</button>
							</li>
						))}
					</ul>
				)}
			</aside>

			{/* Main panel */}
			<main className={`pd-main${fullscreen ? ' pd-fullscreen' : ''}`}>
				{error && (
					<div className="pd-error-banner">
						{error}
						<button onClick={() => setError(null)}>✕</button>
					</div>
				)}

				{!activePortfolio ? (
					<div className="pd-no-selection">
						<p>Select or create a portfolio to get started.</p>
						<button className="pd-btn pd-btn-primary" onClick={() => setShowCreateModal(true)}>Create Portfolio</button>
					</div>
				) : (
					<>
						{/* Portfolio header */}
						<div className="pd-portfolio-header">
							<div>
								<h2 className="pd-portfolio-name">{activePortfolio.name}</h2>
								{activePortfolio.description && (
									<p className="pd-portfolio-desc">{activePortfolio.description}</p>
								)}
							</div>
							<div className="pd-stats-row">
								<div className="pd-stat-card">
									<span className="pd-stat-label">Positions</span>
									<span className="pd-stat-value">{holdings.length}</span>
								</div>
								<div className="pd-stat-card">
									<span className="pd-stat-label">Market Value</span>
									<span className="pd-stat-value">
										{totalMarketValue !== null ? `${displayPrefix}${fmtMoney(totalMarketValue)}` : '—'}
									</span>
								</div>
								<div className="pd-stat-card">
									<span className="pd-stat-label">Cost Basis</span>
									<span className="pd-stat-value">{displayPrefix}{fmtMoney(totalCost)}</span>
								</div>
								<div className="pd-stat-card">
									<span className="pd-stat-label">Unrealized P&L</span>
									<span
										className="pd-stat-value"
										style={{ color: totalPnl === null ? '#888' : totalPnl >= 0 ? '#4caf50' : '#f44336' }}
									>
										{totalPnl !== null
											? `${totalPnl >= 0 ? '+' : ''}${displayPrefix}${fmtMoney(totalPnl)}${totalPnlPct != null ? ` (${totalPnlPct.toFixed(1)}%)` : ''}`
											: '—'}
									</span>
								</div>
								<div className="pd-stat-card">
									<span className="pd-stat-label">Total Fees</span>
									<span className="pd-stat-value pd-stat-fees">{displayPrefix}{fmtMoney(activePortfolio.total_fees ?? 0)}</span>
								</div>
								<div className="pd-stat-card">
									<span className="pd-stat-label">Avg Score</span>
									<span className="pd-stat-value" style={{ color: scoreColor(avgScore) }}>
										{avgScore !== null ? avgScore.toFixed(1) : '—'}
									</span>
								</div>
							</div>
							<div className="pd-fx-bar">
								<div className="pd-currency-toggle">
									<button
										className={`pd-currency-btn${displayCurrency === 'CAD' ? ' pd-currency-active' : ''}`}
										onClick={() => setDisplayCurrency('CAD')}
									>CAD</button>
									<button
										className={`pd-currency-btn${displayCurrency === 'USD' ? ' pd-currency-active' : ''}`}
										onClick={() => setDisplayCurrency('USD')}
									>USD</button>
								</div>
								<span className="pd-fx-note">{fxNote}</span>
							</div>
						</div>

						{/* View tabs + actions */}
						<div className="pd-view-bar">
							<div className="pd-view-tabs">
								<button
									className={`pd-view-tab${activeView === 'holdings' ? ' pd-tab-active' : ''}`}
									onClick={() => setActiveView('holdings')}
								>
									Holdings ({holdings.length})
								</button>
								<button
									className={`pd-view-tab${activeView === 'accounts' ? ' pd-tab-active' : ''}`}
									onClick={() => setActiveView('accounts')}
								>
									Accounts
								</button>
								<button
									className={`pd-view-tab${activeView === 'transactions' ? ' pd-tab-active' : ''}`}
									onClick={() => setActiveView('transactions')}
								>
									Trades ({transactions.length})
								</button>
							</div>
							<div className="pd-view-actions">
								<button
									className="pd-btn pd-btn-ghost pd-btn-sm"
									onClick={handleRefreshScores}
									disabled={refreshing || holdings.length === 0}
									title="Re-fetch data (if cache expired) and re-score all holdings"
								>
									{refreshing ? '↻ Refreshing…' : '↻ Refresh'}
								</button>
								<button className="pd-btn pd-btn-primary pd-btn-sm" onClick={() => setShowTxModal(true)}>
									+ Transaction
								</button>
								<button
									className="pd-icon-btn"
									onClick={() => setFullscreen(f => !f)}
									title={fullscreen ? 'Exit fullscreen' : 'Expand'}
								>
									{fullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
								</button>
							</div>
						</div>

						{/* Content */}
						{loadingDetail ? (
							<div className="pd-loading">Loading…</div>
						) : activeView === 'holdings' ? (
							<HoldingsTable
								holdings={holdings}
								displayCurrency={displayCurrency}
								usdcadRate={usdcadRate}
								fullscreen={fullscreen}
								onTickerClick={openRawDrawer}
								onScoreClick={openWaterfall}
							/>
						) : activeView === 'accounts' ? (
							<AccountsTable
								holdings={holdings}
								onTickerClick={openRawDrawer}
								onScoreClick={openWaterfall}
							/>
						) : (
							<TransactionLedger transactions={transactions} />
						)}
					</>
				)}
			</main>

			{/* Modals */}
			{pendingDelete && (
				<ConfirmDeleteModal
					portfolio={pendingDelete}
					onClose={() => setPendingDelete(null)}
					onConfirm={confirmDelete}
					loading={deleting}
				/>
			)}
			{showCreateModal && (
				<CreatePortfolioModal
					onClose={() => setShowCreateModal(false)}
					onCreated={handlePortfolioCreated}
				/>
			)}
			{showTxModal && activePortfolio && (
				<AddTransactionModal
					portfolioId={activePortfolio.id}
					onClose={() => setShowTxModal(false)}
					onAdded={handleTransactionAdded}
				/>
			)}
			<RawMetricsDrawer
				asset={rawDrawerAsset}
				onClose={() => setRawDrawerAsset(null)}
			/>
			<ScoreWaterfallModal
				asset={waterfallAsset}
				onClose={() => setWaterfallAsset(null)}
			/>
			{loadingWaterfall && (
				<div className="pd-waterfall-loading">
					Scoring {loadingWaterfall}…
				</div>
			)}
		</div>
	)
}
