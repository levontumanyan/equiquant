import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE_URL } from '../config'
import ResultsGrid from './ResultsGrid'
import CorrelationMap from './CorrelationMap'
import type { AssetAnalysis } from '../types'
import { Play, Loader2, AlertCircle, X, Plus, Search, Settings, Square, LayoutGrid, Network } from 'lucide-react'
import './AnalysisPanel.css'

interface Asset {
	symbol: string;
	name: string;
	sector: string | null;
}

interface Group {
	name: string;
	description: string | null;
	is_system: number;
	ticker_count: number;
}

interface AnalysisPanelProps {
	openbbReady: boolean | null;
}

const AnalysisPanel: React.FC<AnalysisPanelProps> = ({ openbbReady }) => {
	const [tickers, setTickers] = useState<string[]>([])
	const [manualInput, setManualInput] = useState('')
	const [availableAssets, setAvailableAssets] = useState<Asset[]>([])
	const [assetSearch, setAssetSearch] = useState('')
	const [profile, setProfile] = useState('balanced')
	const [profiles, setProfiles] = useState<string[]>([])
	const [groups, setGroups] = useState<Group[]>([])
	const [isLoading, setIsLoading] = useState(false)
	const [results, setResults] = useState<AssetAnalysis[]>([])
	const [error, setError] = useState<string | null>(null)
	const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
	const [selectedGroups, setSelectedGroups] = useState<Set<string>>(new Set())
	const groupTickerCache = useRef<Map<string, string[]>>(new Map())
	const abortControllerRef = useRef<AbortController | null>(null)

	const [showNewGroup, setShowNewGroup] = useState(false)
	const [newGroupName, setNewGroupName] = useState('')
	const [newGroupTickers, setNewGroupTickers] = useState('')
	const [newGroupDesc, setNewGroupDesc] = useState('')
	const [groupSaveStatus, setGroupSaveStatus] = useState<'idle' | 'saving' | 'error'>('idle')

	const [provider, setProvider] = useState('openbb')
	const [showSettings, setShowSettings] = useState(false)
	const [viewMode, setViewMode] = useState<'grid' | 'explorer'>('grid')

	const loadGroups = useCallback(async () => {
		try {
			const res = await fetch(`${API_BASE_URL}/api/groups`)
			if (res.ok) setGroups(await res.json())
			else console.error('Failed to load groups:', res.status)
		} catch (err) {
			console.error('Network error loading groups:', err)
		}
	}, [])

	useEffect(() => {
		const fetchInitial = async () => {
			try {
				const [assetsRes, profilesRes] = await Promise.all([
					fetch(`${API_BASE_URL}/api/assets`),
					fetch(`${API_BASE_URL}/api/profiles/list`),
				])
				if (assetsRes.ok) setAvailableAssets(await assetsRes.json())
				if (profilesRes.ok) setProfiles(await profilesRes.json())
			} catch (err) {
				console.error('Failed to fetch initial data', err)
			}
		}
		fetchInitial()
		loadGroups()
	}, [loadGroups])

	const addGroup = async (group: Group) => {
		if (selectedGroups.has(group.name)) {
			const cached = groupTickerCache.current.get(group.name) ?? []
			// Build union of tickers still claimed by every OTHER active group
			const otherClaimed = new Set<string>()
			selectedGroups.forEach(name => {
				if (name !== group.name) {
					groupTickerCache.current.get(name)?.forEach(t => otherClaimed.add(t))
				}
			})
			const safeToRemove = new Set(cached.filter(t => !otherClaimed.has(t)))
			setTickers(prev => prev.filter(t => !safeToRemove.has(t)))
			setSelectedGroups(prev => { const n = new Set(prev); n.delete(group.name); return n })
			return
		}
		try {
			const res = await fetch(`${API_BASE_URL}/api/groups/${encodeURIComponent(group.name)}/tickers`)
			if (!res.ok) return
			const incoming: string[] = await res.json()
			groupTickerCache.current.set(group.name, incoming)
			setTickers(prev => {
				const existing = new Set(prev)
				return [...prev, ...incoming.filter(t => !existing.has(t))]
			})
			setSelectedGroups(prev => new Set([...prev, group.name]))
		} catch {}
	}

	const handleDeleteGroup = async (groupName: string) => {
		try {
			const res = await fetch(`${API_BASE_URL}/api/groups/${encodeURIComponent(groupName)}`, { method: 'DELETE' })
			if (!res.ok) console.error('Failed to delete group:', await res.text())
		} catch (err) {
			console.error('Network error deleting group:', err)
		}
		loadGroups()
	}

	const handleSaveGroup = async () => {
		const name = newGroupName.trim()
		const tickerList = newGroupTickers.split(',').map(t => t.trim()).filter(Boolean)
		if (!name || tickerList.length === 0) return

		setGroupSaveStatus('saving')
		try {
			const res = await fetch(`${API_BASE_URL}/api/groups`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name, tickers: tickerList, description: newGroupDesc.trim() || null }),
			})
			if (res.ok) {
				setNewGroupName('')
				setNewGroupTickers('')
				setNewGroupDesc('')
				setShowNewGroup(false)
				setGroupSaveStatus('idle')
				loadGroups()
			} else {
				console.error('Failed to save group:', await res.text())
				setGroupSaveStatus('error')
			}
		} catch (err) {
			console.error('Network error saving group:', err)
			setGroupSaveStatus('error')
		}
	}

	const filteredAssets = useMemo(() => {
		if (!assetSearch) return []
		const search = assetSearch.toUpperCase()
		return availableAssets
			.filter(a => {
				const symbol = a.symbol?.toUpperCase() || ''
				const name = a.name?.toUpperCase() || ''
				return (symbol.includes(search) || name.includes(search)) &&
					!tickers.includes(a.symbol)
			})
			.slice(0, 8)
	}, [assetSearch, availableAssets, tickers])

	const addTicker = (symbol: string) => {
		const s = symbol.toUpperCase().trim()
		if (s && !tickers.includes(s)) {
			setTickers([...tickers, s])
		}
		setAssetSearch('')
		setManualInput('')
	}

	const removeTicker = (symbol: string) => {
		setTickers(tickers.filter(t => t !== symbol))
	}

	const handleManualSubmit = (e: React.KeyboardEvent) => {
		if (e.key === 'Enter') {
			e.preventDefault()
			addTicker(manualInput)
		}
	}

	const handleRunAnalysis = async () => {
		if (tickers.length === 0) {
			setError('Please select at least one ticker symbol.')
			return
		}

		const controller = new AbortController()
		abortControllerRef.current = controller

		setIsLoading(true)
		setError(null)
		setResults([])
		setProgress({ done: 0, total: tickers.length })

		// Buffer incoming results and flush in batches per animation frame to
		// avoid a full grid rerender on every single SSE event.
		const resultBuffer: AssetAnalysis[] = []
		let flushRaf: number | null = null
		let doneCount = 0

		const scheduleFlush = () => {
			if (flushRaf !== null) return
			flushRaf = requestAnimationFrame(() => {
				const batch = resultBuffer.splice(0)
				if (batch.length > 0) setResults(prev => [...prev, ...batch])
				flushRaf = null
			})
		}

		try {
			await fetchEventSource(`${API_BASE_URL}/api/analyze/stream`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ tickers, profile }),
				signal: controller.signal,
				openWhenHidden: true,
				onmessage(ev) {
					if (ev.event === 'result') {
						const result: AssetAnalysis = JSON.parse(ev.data)
						resultBuffer.push(result)
						doneCount++
						setProgress(prev => prev ? { ...prev, done: doneCount } : null)
						scheduleFlush()
					} else if (ev.event === 'done') {
						if (flushRaf !== null) { cancelAnimationFrame(flushRaf); flushRaf = null }
						const remaining = resultBuffer.splice(0)
						if (remaining.length > 0) setResults(prev => [...prev, ...remaining])
						setIsLoading(false)
						setProgress(null)
					} else if (ev.event === 'error') {
						const err = JSON.parse(ev.data)
						setError(err.message || 'Analysis failed')
						setIsLoading(false)
						setProgress(null)
					}
				},
				onerror(err) {
					if (controller.signal.aborted) return
					setError(err?.message || 'Connection error')
					setIsLoading(false)
					setProgress(null)
					throw err
				},
				onclose() {
					setIsLoading(false)
					setProgress(null)
				},
			})
		} catch (err: any) {
			if (!controller.signal.aborted) {
				setError(err?.message || 'Analysis failed')
			}
			setIsLoading(false)
			setProgress(null)
		}
	}

	const handleCancelAnalysis = () => {
		if (abortControllerRef.current) {
			abortControllerRef.current.abort()
			abortControllerRef.current = null
		}
		setIsLoading(false)
		setProgress(null)
	}

	const systemGroups = groups.filter(g => g.is_system)
	const customGroups = groups.filter(g => !g.is_system)

	return (
		<div className="analysis-panel">
			<div className="analysis-layout">
				{/* Controls Column */}
				<div className="controls-column">
					<div className="controls-card">
						{/* Asset Selection */}
						<div className="input-group">
							<label className="input-label">Select Assets</label>

							{/* Groups */}
							<div className="groups-section">
								<div className="groups-header-row">
									<span className="groups-sublabel">Groups</span>
									<button
										className="new-group-btn"
										onClick={() => { setShowNewGroup(v => !v); setGroupSaveStatus('idle') }}
									>
										{showNewGroup ? 'Cancel' : <><Plus size={11} /> New</>}
									</button>
								</div>

								{showNewGroup && (
									<div className="new-group-form">
										<div className="new-group-fields">
											<input
												type="text"
												placeholder="Group name"
												value={newGroupName}
												onChange={e => setNewGroupName(e.target.value)}
												className="group-input"
											/>
											<input
												type="text"
												placeholder="Description (optional)"
												value={newGroupDesc}
												onChange={e => setNewGroupDesc(e.target.value)}
												className="group-input"
											/>
											<input
												type="text"
												placeholder="Tickers: AAPL, MSFT, GOOGL…"
												value={newGroupTickers}
												onChange={e => setNewGroupTickers(e.target.value)}
												className="group-input group-input--mono"
											/>
										</div>
										<div className="new-group-actions">
											<button
												className="save-group-btn"
												onClick={handleSaveGroup}
												disabled={groupSaveStatus === 'saving' || !newGroupName.trim() || !newGroupTickers.trim()}
											>
												{groupSaveStatus === 'saving' ? 'Saving…' : 'Save Group'}
											</button>
											{groupSaveStatus === 'error' && (
												<span className="group-save-error">Failed to save.</span>
											)}
										</div>
									</div>
								)}

								{groups.length > 0 && (
									<div className="group-chips">
										{systemGroups.map(g => (
											<button
												key={g.name}
												className={`group-chip group-chip--system${selectedGroups.has(g.name) ? ' group-chip--active' : ''}`}
												onClick={() => addGroup(g)}
												title={g.description ?? undefined}
											>
												★ {g.name}
												{g.ticker_count > 0 && <span className="group-chip-count">{g.ticker_count}</span>}
											</button>
										))}
										{customGroups.map(g => (
											<div key={g.name} className="group-chip-wrap">
												<button
													className={`group-chip${selectedGroups.has(g.name) ? ' group-chip--active' : ''}`}
													onClick={() => addGroup(g)}
													title={g.description ?? undefined}
												>
													{g.name}
													{g.ticker_count > 0 && <span className="group-chip-count">{g.ticker_count}</span>}
												</button>
												<button
													className="group-chip-delete"
													onClick={() => handleDeleteGroup(g.name)}
													aria-label={`Delete ${g.name}`}
												>
													<X size={9} />
												</button>
											</div>
										))}
									</div>
								)}
							</div>

							{/* Ticker Picker */}
							<div className="ticker-picker">
								{tickers.length > 0 && (
									<span className="ticker-total">{tickers.length} selected</span>
								)}
								<div className="search-bar">
									<Search size={14} className="search-icon" />
									<input
										type="text"
										value={assetSearch || manualInput}
										onChange={(e) => {
											setAssetSearch(e.target.value)
											setManualInput(e.target.value)
										}}
										onKeyDown={handleManualSubmit}
										placeholder="Search or type ticker"
										className="ticker-input"
									/>
									{manualInput && (
										<button className="add-manual-btn" onClick={() => addTicker(manualInput)}>
											<Plus size={14} />
										</button>
									)}
								</div>

								{filteredAssets.length > 0 && (
									<div className="asset-dropdown">
										{filteredAssets.map(asset => (
											<button
												key={asset.symbol}
												className="dropdown-item"
												onClick={() => addTicker(asset.symbol)}
											>
												<span className="item-symbol">{asset.symbol}</span>
												<span className="item-name">{asset.name}</span>
											</button>
										))}
									</div>
								)}

								<div className="ticker-chips">
									{tickers.map(t => (
										<div key={t} className="ticker-chip">
											<span>{t}</span>
											<button onClick={() => removeTicker(t)} className="remove-chip">
												<X size={10} />
											</button>
										</div>
									))}
									{tickers.length === 0 && (
										<p className="empty-chips-text">No assets selected</p>
									)}
								</div>
							</div>

							<div className="quick-actions">
								<button
									className="action-link"
									onClick={() => setTickers(availableAssets.map(a => a.symbol))}
								>
									Select All ({availableAssets.length})
								</button>
								<button
									className="action-link text-red"
									onClick={() => { setTickers([]); setSelectedGroups(new Set()) }}
								>
									Clear
								</button>
							</div>
						</div>

						{/* Investor Profile */}
						<div className="input-group">
							<label className="input-label">Investor Profile</label>
							<select
								value={profile}
								onChange={(e) => setProfile(e.target.value)}
								className="profile-select"
							>
								{profiles.map(p => (
									<option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
								))}
							</select>
						</div>

						{/* Run / Cancel Buttons */}
						<button
							onClick={handleRunAnalysis}
							disabled={isLoading || !openbbReady}
							className={`run-button ${isLoading ? 'loading' : 'idle'}`}
						>
							{isLoading ? (
								<Loader2 className="spin" size={20} />
							) : (
								<Play size={18} fill="currentColor" />
							)}
							{isLoading
								? progress
									? `Analyzing… ${progress.done}/${progress.total}`
									: 'Fetching data…'
								: 'Run Analysis'}
						</button>
						{isLoading && (
							<button onClick={handleCancelAnalysis} className="cancel-button">
								<Square size={14} fill="currentColor" />
								Cancel
							</button>
						)}

						{/* Settings (Provider) */}
						<div className="settings-row">
							<button
								className="settings-toggle"
								onClick={() => setShowSettings(v => !v)}
								aria-label="Toggle advanced options"
							>
								<Settings size={13} />
								<span>Advanced Options</span>
							</button>
							{showSettings && (
								<div className="settings-panel">
									<label className="settings-label">Data Provider</label>
									<select
										value={provider}
										onChange={e => setProvider(e.target.value)}
										className="provider-select"
									>
										<option value="openbb">OpenBB (Default)</option>
										<option value="nasdaq" disabled>Nasdaq Data Link (Coming Soon)</option>
									</select>
								</div>
							)}
						</div>

						{openbbReady === false && (
							<div className="warming-up-box">
								<Loader2 className="spin" size={13} />
								<span>Warming up data provider — ready in a few seconds…</span>
							</div>
						)}

						{error && (
							<div className="error-box">
								<AlertCircle size={14} className="error-icon" />
								<span>{error}</span>
							</div>
						)}
					</div>
				</div>

				{/* Results Column */}
				<div className="results-column">
					{results.length > 0 && (
						<div className="view-toggle">
							<button
								className={`view-toggle-btn${viewMode === 'grid' ? ' active' : ''}`}
								onClick={() => setViewMode('grid')}
								title="Data Grid"
							>
								<LayoutGrid size={13} />
								Grid
							</button>
							<button
								className={`view-toggle-btn${viewMode === 'explorer' ? ' active' : ''}`}
								onClick={() => setViewMode('explorer')}
								title="Cluster Map"
							>
								<Network size={13} />
								Cluster Map
							</button>
						</div>
					)}
					{viewMode === 'grid' || results.length === 0
						? <ResultsGrid data={results} profile={profile} />
						: <CorrelationMap data={results} />
					}
				</div>
			</div>
		</div>
	)
}

export default AnalysisPanel
