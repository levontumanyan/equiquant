import React, { useMemo, useState, useEffect } from 'react'
import { Search, Copy, Check, X, Loader2 } from 'lucide-react'
import type { AssetAnalysis } from '../types'
import './RawMetricsDrawer.css'

interface RawMetricsDrawerProps {
	asset: AssetAnalysis | null
	onClose: () => void
}

function formatValue(val: unknown): { text: string; cls: string; url?: string } {
	if (val === null || val === undefined) return { text: '—', cls: 'raw-val-null' }
	if (typeof val === 'boolean') return { text: val ? 'Yes' : 'No', cls: 'raw-val-bool' }
	if (typeof val === 'number') {
		const text = Number.isInteger(val)
			? val.toLocaleString()
			: val.toFixed(6).replace(/\.?0+$/, '')
		return { text, cls: 'raw-val-num' }
	}
	if (typeof val === 'string') {
		const isUrl = /^https?:\/\//i.test(val)
		const display = val.replace(/^https?:\/\/(www\.)?/, '') || '—'
		return { text: display, cls: val ? 'raw-val-str' : 'raw-val-null', url: isUrl ? val : undefined }
	}
	return { text: JSON.stringify(val), cls: 'raw-val-obj' }
}

const CLAMP_THRESHOLD = 120

const RawMetricsDrawer: React.FC<RawMetricsDrawerProps> = ({ asset, onClose }) => {
	const [search, setSearch] = useState('')
	const [copied, setCopied] = useState(false)
	const [expanded, setExpanded] = useState<Set<string>>(new Set())
	const [hideNulls, setHideNulls] = useState(true)
	const [rawData, setRawData] = useState<Record<string, unknown> | null>(null)
	const [loading, setLoading] = useState(false)
	const [fetchError, setFetchError] = useState<string | null>(null)

	useEffect(() => {
		setSearch('')
		setExpanded(new Set())
		setRawData(null)
		setFetchError(null)

		if (!asset) return

		setLoading(true)
		fetch(`/api/assets/${encodeURIComponent(asset.symbol)}/raw`)
			.then(res => {
				if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
				return res.json() as Promise<Record<string, unknown>>
			})
			.then(data => {
				setRawData(data)
				setLoading(false)
			})
			.catch(err => {
				setFetchError((err as Error).message)
				setLoading(false)
			})
	}, [asset?.symbol])

	const toggleExpand = (key: string) =>
		setExpanded(prev => {
			const next = new Set(prev)
			next.has(key) ? next.delete(key) : next.add(key)
			return next
		})

	useEffect(() => {
		const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
		window.addEventListener('keydown', handler)
		return () => window.removeEventListener('keydown', handler)
	}, [onClose])

	const allEntries = useMemo(() => {
		if (!rawData) return []
		return Object.entries(rawData).sort(([a], [b]) => a.localeCompare(b))
	}, [rawData])

	const entries = useMemo(() => {
		let result = allEntries
		if (hideNulls) result = result.filter(([, v]) => v !== null && v !== undefined)
		if (search) {
			const q = search.toLowerCase()
			result = result.filter(([k]) => k.toLowerCase().includes(q))
		}
		return result
	}, [allEntries, search, hideNulls])

	const handleCopy = () => {
		if (!rawData) return
		navigator.clipboard.writeText(JSON.stringify(rawData, null, 2))
		setCopied(true)
		setTimeout(() => setCopied(false), 2000)
	}

	const open = asset !== null

	return (
		<>
			{open && <div className="raw-drawer-backdrop" onClick={onClose} />}
			<div className={`raw-drawer${open ? ' raw-drawer--open' : ''}`} aria-hidden={!open}>
				{asset && (
					<>
						<div className="raw-drawer-header">
							<div className="raw-drawer-title">
								<span className="raw-drawer-symbol">{asset.symbol}</span>
								<span className="raw-drawer-name">{asset.name}</span>
							</div>
							<div className="raw-drawer-actions">
								<button
									className="raw-drawer-icon-btn"
									onClick={handleCopy}
									title="Copy raw JSON"
									disabled={!rawData}
								>
									{copied ? <Check size={14} /> : <Copy size={14} />}
								</button>
								<button
									className="raw-drawer-icon-btn"
									onClick={onClose}
									title="Close"
								>
									<X size={14} />
								</button>
							</div>
						</div>

						<div className="raw-drawer-search">
							<Search size={13} className="raw-drawer-search-icon" />
							<input
								placeholder="Filter keys…"
								value={search}
								onChange={e => setSearch(e.target.value)}
								autoFocus
								disabled={loading || !rawData}
							/>
							<span className="raw-drawer-count">
								{entries.length} / {allEntries.length}
							</span>
							<button
								className={`raw-null-toggle${hideNulls ? ' raw-null-toggle--on' : ''}`}
								onClick={() => setHideNulls(v => !v)}
								title={hideNulls ? 'Show empty fields' : 'Hide empty fields'}
							>
								{hideNulls ? 'N/A hidden' : 'N/A shown'}
							</button>
						</div>

						<div className="raw-drawer-body">
							{loading ? (
								<p className="raw-drawer-empty">
									<Loader2 size={14} className="raw-drawer-spinner" /> Loading…
								</p>
							) : fetchError ? (
								<p className="raw-drawer-empty">
									Failed to load: {fetchError}
								</p>
							) : !rawData ? (
								<p className="raw-drawer-empty">
									No raw data — re-run analysis to populate.
								</p>
							) : entries.length === 0 ? (
								<p className="raw-drawer-empty">No keys match "{search}"</p>
							) : (
								<table className="raw-drawer-table">
									<tbody>
										{entries.map(([key, val]) => {
											const { text, cls, url } = formatValue(val)
											const isNull = val === null || val === undefined
											const isLong = cls === 'raw-val-str' && text.length > CLAMP_THRESHOLD
											const isExpanded = expanded.has(key)
											return (
												<tr key={key} className={isNull ? 'raw-row-null' : ''}>
													<td className="raw-key">{key}</td>
													<td
														className={`raw-val ${cls}${isLong && !isExpanded ? ' raw-val-clamped' : ''}`}
														style={isLong && isExpanded ? { textAlign: 'left', cursor: 'pointer' } : undefined}
														onClick={isLong ? () => toggleExpand(key) : undefined}
														title={isLong ? (isExpanded ? 'Click to collapse' : 'Click to expand') : undefined}
													>
														{url ? (
															<a
																className="raw-val-link"
																href={url}
																target="_blank"
																rel="noopener noreferrer"
																onClick={e => e.stopPropagation()}
															>
																{text}
															</a>
														) : text}
														{isLong && (
															<span className="raw-expand-hint">
																{isExpanded ? ' less' : ' more'}
															</span>
														)}
													</td>
												</tr>
											)
										})}
									</tbody>
								</table>
							)}
						</div>

						<div className="raw-drawer-footer">
							{allEntries.length} fields · {allEntries.filter(([, v]) => v !== null && v !== undefined).length} populated
						</div>
					</>
				)}
			</div>
		</>
	)
}

export default RawMetricsDrawer
