import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE_URL } from '../config'
import { useProfiles } from '../hooks/useProfiles'
import ResultsGrid from './ResultsGrid'
import CorrelationMap from './CorrelationMap'
import SmartHeatmap from './SmartHeatmap'
import type { AssetAnalysis } from '../types'
import { Play, Loader2, AlertCircle, X, Plus, Search, Settings, Square, LayoutGrid, Network, LayoutDashboard, FileText } from 'lucide-react'
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
	const { profiles } = useProfiles()
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
	const [newGroupTickers, setNewGroupTickers] = useState<string[]>([])
	const [newGroupSearch, setNewGroupSearch] = useState('')
	const [newGroupDesc, setNewGroupDesc] = useState('')
	const [groupSaveStatus, setGroupSaveStatus] = useState<'idle' | 'saving' | 'error'>('idle')

	const [provider, setProvider] = useState('openbb')
	const [showSettings, setShowSettings] = useState(false)
	const [viewMode, setViewMode] = useState<'grid' | 'explorer' | 'heatmap'>('grid')
	const [heatmapFilter, setHeatmapFilter] = useState('')
	const [isExporting, setIsExporting] = useState<string | null>(null)

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
				const assetsRes = await fetch(`${API_BASE_URL}/api/assets`)
				if (assetsRes.ok) setAvailableAssets(await assetsRes.json())
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
		if (!name || newGroupTickers.length === 0) return

		setGroupSaveStatus('saving')
		try {
			const res = await fetch(`${API_BASE_URL}/api/groups`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name, tickers: newGroupTickers, description: newGroupDesc.trim() || null }),
			})
			if (res.ok) {
				setNewGroupName('')
				setNewGroupTickers([])
				setNewGroupSearch('')
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

	const newGroupFilteredAssets = useMemo(() => {
		if (!newGroupSearch) return []
		const search = newGroupSearch.toUpperCase()
		return availableAssets
			.filter(a => {
				const symbol = a.symbol?.toUpperCase() || ''
				const name = a.name?.toUpperCase() || ''
				return (symbol.includes(search) || name.includes(search)) &&
					!newGroupTickers.includes(a.symbol)
			})
			.slice(0, 8)
	}, [newGroupSearch, availableAssets, newGroupTickers])

	const addNewGroupTicker = (symbol: string) => {
		const input = symbol.toUpperCase().trim()
		if (!input) return

		const newSymbols = input.split(/[,\s]+/).map(s => s.trim()).filter(s => s && !newGroupTickers.includes(s))
		if (newSymbols.length > 0) {
			setNewGroupTickers([...newGroupTickers, ...newSymbols])
		}
		setNewGroupSearch('')
	}

	const removeNewGroupTicker = (symbol: string) => {
		setNewGroupTickers(newGroupTickers.filter(t => t !== symbol))
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
		const input = symbol.toUpperCase().trim()
		if (!input) return

		const newSymbols = input.split(/[,\s]+/).map(s => s.trim()).filter(s => s && !tickers.includes(s))
		if (newSymbols.length > 0) {
			setTickers([...tickers, ...newSymbols])
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
		setHeatmapFilter('')
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

	const handleExport = async (format: 'csv' | 'txt') => {
		if (results.length === 0) return
		setIsExporting(format)
		try {
			const response = await fetch(`${API_BASE_URL}/api/export`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					results,
					format,
					profile,
					tickers,
					index_name: selectedGroups.size === 1 ? Array.from(selectedGroups)[0] : null
				}),
			})
			if (response.ok) {
				const blob = await response.blob()
				const url = window.URL.createObjectURL(blob)
				const a = document.createElement('a')
				a.href = url
				const contentDisposition = response.headers.get('content-disposition')
				a.download = contentDisposition?.split('filename=')[1]?.split(';')[0]?.replace(/"/g, '').trim() || `export.${format}`
				document.body.appendChild(a)
				a.click()
				a.remove()
				window.URL.revokeObjectURL(url)
			} else {
				console.error('Export failed:', await response.text())
			}
		} catch (err) {
			console.error('Export error:', err)
		} finally {
			setIsExporting(null)
		}
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
											
											{/* Unified Ticker Picker for New Group */}
											<div className="ticker-picker ticker-picker--compact">
												<div className="search-bar">
													<Search size={14} className="search-icon" />
													<input
														type="text"
														value={newGroupSearch}
														onChange={(e) => setNewGroupSearch(e.target.value)}
														onKeyDown={(e) => {
															if (e.key === 'Enter') {
																e.preventDefault()
																addNewGroupTicker(newGroupSearch)
															}
														}}
														placeholder="Add tickers to group"
														className="ticker-input"
													/>
													{newGroupSearch && (
														<button className="add-manual-btn" onClick={() => addNewGroupTicker(newGroupSearch)}>
															<Plus size={14} />
														</button>
													)}
												</div>

												{newGroupFilteredAssets.length > 0 && (
													<div className="asset-dropdown">
														{newGroupFilteredAssets.map(asset => (
															<button
																key={asset.symbol}
																className="dropdown-item"
																onClick={() => addNewGroupTicker(asset.symbol)}
															>
																<span className="item-symbol">{asset.symbol}</span>
																<span className="item-name">{asset.name}</span>
															</button>
														))}
													</div>
												)}

												<div className="ticker-chips">
													{newGroupTickers.map(t => (
														<div key={t} className="ticker-chip">
															<span>{t}</span>
															<button onClick={() => removeNewGroupTicker(t)} className="remove-chip">
																<X size={10} />
															</button>
														</div>
													))}
													{newGroupTickers.length === 0 && (
														<p className="empty-chips-text">No tickers added</p>
													)}
												</div>
											</div>
										</div>
										<div className="new-group-actions">
											<button
												className="save-group-btn"
												onClick={handleSaveGroup}
												disabled={groupSaveStatus === 'saving' || !newGroupName.trim() || newGroupTickers.length === 0}
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
						<div className="results-header-actions">
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
									className={`view-toggle-btn${viewMode === 'heatmap' ? ' active' : ''}`}
									onClick={() => setViewMode('heatmap')}
									title="Sector Heatmap"
								>
									<LayoutDashboard size={13} />
									Heatmap
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

							<div className="export-actions">
								<button 
									className="export-btn" 
									onClick={() => handleExport('csv')}
									disabled={isExporting !== null}
								>
									{isExporting === 'csv' ? <Loader2 size={13} className="spin" /> : <FileText size={13} />}
									Export CSV
								</button>
								<button 
									className="export-btn" 
									onClick={() => handleExport('txt')}
									disabled={isExporting !== null}
								>
									{isExporting === 'txt' ? <Loader2 size={13} className="spin" /> : <FileText size={13} />}
									Export TXT
								</button>
							</div>
						</div>
					)}
					{results.length === 0 || viewMode === 'grid'
						? <ResultsGrid data={results} profile={profile} externalFilter={heatmapFilter} />
						: viewMode === 'explorer'
							? <CorrelationMap data={results} />
							: <SmartHeatmap
								data={results}
								onSelectSymbol={(sym) => {
									setHeatmapFilter(sym)
									setViewMode('grid')
								}}
							/>
					}
				</div>
			</div>
		</div>
	)
}

export default AnalysisPanel
