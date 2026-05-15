import React, { useState, useEffect, useMemo } from 'react'
import ResultsGrid from './ResultsGrid'
import type { AssetAnalysis } from '../types'
import { Play, Loader2, AlertCircle, X, Plus, Search } from 'lucide-react'
import './AnalysisPanel.css'

interface Asset {
	symbol: string;
	name: string;
	sector: string | null;
}

const AnalysisPanel: React.FC = () => {
	const [tickers, setTickers] = useState<string[]>([])
	const [manualInput, setManualInput] = useState('')
	const [availableAssets, setAvailableAssets] = useState<Asset[]>([])
	const [assetSearch, setAssetSearch] = useState('')
	const [profile, setProfile] = useState('balanced')
	const [profiles, setProfiles] = useState<string[]>([])
	const [isLoading, setIsLoading] = useState(false)
	const [results, setResults] = useState<AssetAnalysis[]>([])
	const [error, setError] = useState<string | null>(null)

	useEffect(() => {
		const fetchData = async () => {
			try {
				const [assetsRes, statusRes] = await Promise.all([
					fetch('http://localhost:8000/api/assets'),
					fetch('http://localhost:8000/api/status')
				])
				
				if (assetsRes.ok) {
					const assets = await assetsRes.json()
					setAvailableAssets(assets)
				}
				
				setProfiles(['balanced', 'growth', 'dividend'])
			} catch (err) {
				console.error('Failed to fetch initial data', err)
			}
		}
		fetchData()
	}, [])

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
			const response = await fetch('http://localhost:8000/api/analyze', {
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

	return (
		<div className="analysis-panel">
			<div className="analysis-layout">
				{/* Controls Column */}
				<div className="controls-column">
					<div className="controls-card">
						<div className="input-group">
							<label className="input-label">Select Assets</label>
							
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
										placeholder="Search"
										className="ticker-input"
									/>
									{manualInput && (
										<button className="add-manual-btn" onClick={() => addTicker(manualInput)}>
											<Plus size={14} />
										</button>
									)}
								</div>

								{/* Autocomplete Dropdown */}
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

								{/* Selected Chips */}
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

						<button
							onClick={handleRunAnalysis}
							disabled={isLoading}
							className={`run-button ${isLoading ? 'loading' : 'idle'}`}
						>
							{isLoading ? (
								<Loader2 className="spin" size={20} />
							) : (
								<Play size={18} fill="currentColor" />
							)}
							{isLoading ? 'Analyzing...' : 'Run Analysis'}
						</button>

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

