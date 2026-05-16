import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { API_BASE_URL } from '../config'
import ResultsGrid from './ResultsGrid'
import type { AssetAnalysis } from '../types'
import { Play, Loader2, AlertCircle, X, Plus, Search, Settings } from 'lucide-react'
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
}

interface AnalysisPanelProps {
	openbbReady: boolean;
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

	const [showNewGroup, setShowNewGroup] = useState(false)
	const [newGroupName, setNewGroupName] = useState('')
	const [newGroupTickers, setNewGroupTickers] = useState('')
	const [newGroupDesc, setNewGroupDesc] = useState('')
	const [groupSaveStatus, setGroupSaveStatus] = useState<'idle' | 'saving' | 'error'>('idle')

	const [provider, setProvider] = useState('openbb')
	const [showSettings, setShowSettings] = useState(false)

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
		try {
			const res = await fetch(`${API_BASE_URL}/api/groups/${encodeURIComponent(group.name)}/tickers`)
			if (!res.ok) return
			const incoming: string[] = await res.json()
			setTickers(prev => {
				const existing = new Set(prev)
				return [...prev, ...incoming.filter(t => !existing.has(t))]
			})
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

		setIsLoading(true)
		setError(null)

		try {
			const response = await fetch(`${API_BASE_URL}/api/analyze`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					tickers: tickers,
					profile: profile,
				}),
			})

			if (!response.ok) {
				const detail = await response.json()
				throw new Error(detail.detail || 'Analysis failed')
			}

			const data = await response.json()
			setResults(data)
		} catch (err: any) {
			setError(err.message)
		} finally {
			setIsLoading(false)
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
												className="group-chip group-chip--system"
												onClick={() => addGroup(g)}
												title={g.description ?? undefined}
											>
												★ {g.name}
											</button>
										))}
										{customGroups.map(g => (
											<div key={g.name} className="group-chip-wrap">
												<button
													className="group-chip"
													onClick={() => addGroup(g)}
													title={g.description ?? undefined}
												>
													{g.name}
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
									onClick={() => setTickers([])}
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

						{/* Run Button */}
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
							{isLoading ? 'Fetching & Analyzing…' : 'Run Analysis'}
						</button>

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

						{!openbbReady && (
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
					<ResultsGrid data={results} />
				</div>
			</div>
		</div>
	)
}

export default AnalysisPanel
