import { useState, useEffect, useCallback } from 'react'
import { Maximize2, Minimize2 } from 'lucide-react'
import { API_BASE_URL } from '../config'
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
	latest_score: number | null
}

interface Transaction {
	id: number
	portfolio_id: number
	symbol: string
	transaction_type: 'BUY' | 'SELL' | 'DIVIDEND'
	quantity: number
	price_per_share: number
	transaction_date: string
	fees: number
	notes: string | null
	created_at: string
}

type ActiveView = 'holdings' | 'transactions'

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

	async function handleSubmit(e: React.FormEvent) {
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
	const [notes, setNotes] = useState('')
	const [error, setError] = useState<string | null>(null)
	const [loading, setLoading] = useState(false)

	async function handleSubmit(e: React.FormEvent) {
		e.preventDefault()
		if (!symbol.trim() || !quantity || !price) { setError('Symbol, quantity, and price are required'); return }
		setLoading(true)
		setError(null)
		try {
			const res = await fetch(`${API_BASE_URL}/api/portfolios/${portfolioId}/transactions`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					symbol: symbol.trim().toUpperCase(),
					transaction_type: type,
					quantity: parseFloat(quantity),
					price_per_share: parseFloat(price),
					transaction_date: date,
					fees: parseFloat(fees) || 0,
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
							Quantity
							<input type="number" min="0" step="any" value={quantity} onChange={e => setQuantity(e.target.value)} placeholder="100" />
						</label>
						<label>
							Price / Share
							<input type="number" min="0" step="any" value={price} onChange={e => setPrice(e.target.value)} placeholder="150.00" />
						</label>
					</div>
					<div className="pd-form-row">
						<label>
							Date
							<input type="date" value={date} onChange={e => setDate(e.target.value)} />
						</label>
						<label>
							Fees
							<input type="number" min="0" step="any" value={fees} onChange={e => setFees(e.target.value)} placeholder="0.00" />
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

// ── Holdings table ─────────────────────────────────────────────────────────

function HoldingsTable({ holdings }: { holdings: Holding[] }) {
	if (holdings.length === 0) {
		return (
			<div className="pd-empty">
				<p>No holdings yet. Use <strong>+ Transaction</strong> to record your first trade.</p>
			</div>
		)
	}

	return (
		<div className="pd-table-wrap">
			<table className="pd-table">
				<thead>
					<tr>
						<th>Symbol</th>
						<th>Name</th>
						<th>Sector</th>
						<th className="pd-right">Shares</th>
						<th className="pd-right">Avg Cost</th>
						<th className="pd-right">Price</th>
						<th className="pd-right">Market Value</th>
						<th className="pd-right">Unrealized P&L</th>
						<th className="pd-right">Score</th>
					</tr>
				</thead>
				<tbody>
					{holdings.map(h => {
						const pnlColor = h.unrealized_pnl === null ? '#888' : h.unrealized_pnl >= 0 ? '#4caf50' : '#f44336'
						return (
							<tr key={h.symbol}>
								<td className="pd-symbol">{h.symbol}</td>
								<td>{h.name ?? '—'}</td>
								<td>{h.sector ?? '—'}</td>
								<td className="pd-right">{h.total_shares.toLocaleString(undefined, { maximumFractionDigits: 4 })}</td>
								<td className="pd-right">${fmtMoney(h.average_cost)}</td>
								<td className="pd-right">
									{h.current_price !== null ? `$${fmtMoney(h.current_price)}` : <span className="pd-muted">—</span>}
								</td>
								<td className="pd-right">
									{h.market_value !== null ? `$${fmtMoney(h.market_value)}` : <span className="pd-muted">—</span>}
								</td>
								<td className="pd-right" style={{ color: pnlColor }}>
									{h.unrealized_pnl !== null
										? `${h.unrealized_pnl >= 0 ? '+' : ''}$${fmtMoney(h.unrealized_pnl)} (${h.unrealized_pnl_pct?.toFixed(1)}%)`
										: <span className="pd-muted">—</span>}
								</td>
								<td className="pd-right">
									{h.latest_score !== null
										? <span className="pd-score-chip" style={{ color: scoreColor(h.latest_score) }}>{h.latest_score.toFixed(1)}</span>
										: <span className="pd-score-chip pd-score-na">—</span>}
								</td>
							</tr>
						)
					})}
				</tbody>
			</table>
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
						<th className="pd-right">Qty</th>
						<th className="pd-right">Price</th>
						<th className="pd-right">Fees</th>
						<th className="pd-right">Total</th>
						<th>Notes</th>
					</tr>
				</thead>
				<tbody>
					{transactions.map(tx => {
						const total = tx.quantity * tx.price_per_share + tx.fees
						return (
							<tr key={tx.id}>
								<td className="pd-muted">{fmtDate(tx.transaction_date)}</td>
								<td className="pd-symbol">{tx.symbol}</td>
								<td>
									<span className={`pd-badge pd-badge-${tx.transaction_type.toLowerCase()}`}>
										{tx.transaction_type}
									</span>
								</td>
								<td className="pd-right">{tx.quantity.toLocaleString(undefined, { maximumFractionDigits: 4 })}</td>
								<td className="pd-right">${fmtMoney(tx.price_per_share)}</td>
								<td className="pd-right">${fmtMoney(tx.fees)}</td>
								<td className="pd-right">${fmtMoney(total)}</td>
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

	// Fetch portfolios list
	const fetchPortfolios = useCallback(async () => {
		setLoadingPortfolios(true)
		try {
			const res = await fetch(`${API_BASE_URL}/api/portfolios`)
			if (!res.ok) throw new Error('Failed to load portfolios')
			const data: Portfolio[] = await res.json()
			setPortfolios(data)
			// Auto-select first if none selected
			if (data.length > 0 && !activePortfolio) {
				setActivePortfolio(data[0])
			}
		} catch (err: any) {
			setError(err.message)
		} finally {
			setLoadingPortfolios(false)
		}
	}, [activePortfolio])

	useEffect(() => { fetchPortfolios() }, [])

	// Fetch holdings + transactions when active portfolio changes
	useEffect(() => {
		if (!activePortfolio) { setHoldings([]); setTransactions([]); return }
		setLoadingDetail(true)
		Promise.all([
			fetch(`${API_BASE_URL}/api/portfolios/${activePortfolio.id}/holdings`).then(r => r.json()),
			fetch(`${API_BASE_URL}/api/portfolios/${activePortfolio.id}/transactions`).then(r => r.json()),
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

	// Summary stats
	const totalCost = holdings.reduce((sum, h) => sum + h.cost_basis, 0)
	const totalMarketValue = holdings.every(h => h.market_value === null)
		? null
		: holdings.reduce((sum, h) => sum + (h.market_value ?? h.cost_basis), 0)
	const totalPnl = totalMarketValue !== null ? totalMarketValue - totalCost : null
	const totalPnlPct = totalPnl !== null && totalCost > 0 ? (totalPnl / totalCost) * 100 : null
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
										{totalMarketValue !== null ? `$${fmtMoney(totalMarketValue)}` : '—'}
									</span>
								</div>
								<div className="pd-stat-card">
									<span className="pd-stat-label">Cost Basis</span>
									<span className="pd-stat-value">${fmtMoney(totalCost)}</span>
								</div>
								<div className="pd-stat-card">
									<span className="pd-stat-label">Unrealized P&L</span>
									<span
										className="pd-stat-value"
										style={{ color: totalPnl === null ? '#888' : totalPnl >= 0 ? '#4caf50' : '#f44336' }}
									>
										{totalPnl !== null
											? `${totalPnl >= 0 ? '+' : ''}$${fmtMoney(totalPnl)} (${totalPnlPct?.toFixed(1)}%)`
											: '—'}
									</span>
								</div>
								<div className="pd-stat-card">
									<span className="pd-stat-label">Total Fees</span>
									<span className="pd-stat-value pd-stat-fees">${fmtMoney(activePortfolio.total_fees ?? 0)}</span>
								</div>
								<div className="pd-stat-card">
									<span className="pd-stat-label">Avg Score</span>
									<span className="pd-stat-value" style={{ color: scoreColor(avgScore) }}>
										{avgScore !== null ? avgScore.toFixed(1) : '—'}
									</span>
								</div>
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
							<HoldingsTable holdings={holdings} />
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
		</div>
	)
}
