import React, { useState, useRef, useMemo } from 'react'
import { Plus, X, Search, BarChart2, BookOpen, Download, ArrowLeft } from 'lucide-react'
import { API_BASE_URL } from '../config'
import { useBenchmarks } from '../hooks/useBenchmarks'
import { useProfiles } from '../hooks/useProfiles'
import { useFormulas } from '../hooks/useFormulas'
import type { Benchmark, ScorerType } from '../types'
import type { StudioMetric } from '../types/studio'
import ScoringExplorer from './ScoringExplorer'
import MetricHistory from './MetricHistory'
import './ScoringStudio.css'

const parseNum = (v: string): number | undefined => {
	const n = parseFloat(v)
	return isNaN(n) ? undefined : n
}

const FORMULA_LABELS: Record<string, string> = {
	sigmoid: 'Sigmoid',
	linear: 'Linear',
	bell_curve: 'Bell',
	plateau: 'Plateau',
	threshold: 'Thresh',
}

type StudioMode = 'landing' | 'importing' | 'active'

const ScoringStudio: React.FC = () => {
	const { benchmarks: allBenchmarks, loading: benchmarksLoading } = useBenchmarks()
	const { profiles: profileNames, refetch: refetchProfiles } = useProfiles()
	const { formulas: availableFormulas } = useFormulas()
	const loading = benchmarksLoading

	const [mode, setMode] = useState<StudioMode>('landing')
	const [activeMetrics, setActiveMetrics] = useState<StudioMetric[]>([])
	const [profileName, setProfileName] = useState('')
	const [sourceProfileName, setSourceProfileName] = useState<string | null>(null)
	const [selectedMetricKey, setSelectedMetricKey] = useState<string | null>(null)

	const [drawerOpen, setDrawerOpen] = useState(false)
	const [drawerSearch, setDrawerSearch] = useState('')
	const [drawerHistoryKey, setDrawerHistoryKey] = useState<string | null>(null)

	const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
	const [overwriteTarget, setOverwriteTarget] = useState<string | null>(null)

	const profileLoadRef = useRef(0)
	const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
	const nameInputRef = useRef<HTMLInputElement>(null)

	const selectedMetric = useMemo(
		() => activeMetrics.find(m => m.metric === selectedMetricKey) ?? null,
		[activeMetrics, selectedMetricKey]
	)

	const activeKeys = useMemo(() => new Set(activeMetrics.map(m => m.metric)), [activeMetrics])

	const totalWeight = useMemo(
		() => activeMetrics.reduce((sum, m) => sum + (m.weight || 0), 0),
		[activeMetrics]
	)

	const profileNameConflict = useMemo(
		() => profileName.trim().length > 0 &&
			profileNames.includes(profileName.trim()) &&
			profileName.trim() !== sourceProfileName,
		[profileName, profileNames, sourceProfileName]
	)

	const filteredDrawerBenchmarks = useMemo(() => {
		const q = drawerSearch.toLowerCase()
		if (!q) return allBenchmarks
		return allBenchmarks.filter(
			b => b.name.toLowerCase().includes(q) || b.metric.toLowerCase().includes(q)
		)
	}, [allBenchmarks, drawerSearch])

	const loadProfileData = async (name: string, benchmarks: Benchmark[]) => {
		const requestId = ++profileLoadRef.current
		try {
			const res = await fetch(`${API_BASE_URL}/api/profiles/${encodeURIComponent(name)}`)
			if (!res.ok) return
			const profile: {
				name: string
				weights: Record<string, number>
				ranges: Record<string, { min: number; max: number }>
				formulas: Record<string, string>
			} = await res.json()
			if (requestId !== profileLoadRef.current) return

			const merged: StudioMetric[] = Object.entries(profile.weights)
				.filter(([, w]) => w > 0)
				.map(([key, w]) => {
					const bench = benchmarks.find(b => b.metric === key)
					const range = profile.ranges[key] ?? { min: 0, max: 100 }
					const formula = profile.formulas[key] ?? 'sigmoid'
					return {
						metric: key,
						name: bench?.name ?? key,
						asset_type: bench?.asset_type ?? 'STOCK',
						unit: bench?.unit,
						is_decimal: bench?.is_decimal,
						type: (bench?.type ?? 'sigmoid') as ScorerType,
						best: bench?.best,
						worst: bench?.worst,
						target: bench?.target,
						target_min: bench?.target_min,
						target_max: bench?.target_max,
						width: bench?.width,
						threshold: bench?.threshold,
						weight: w,
						range_min: range.min,
						range_max: range.max,
						formula,
					}
				})

			setActiveMetrics(merged)
			setSelectedMetricKey(merged[0]?.metric ?? null)
			setProfileName(name)
			setSourceProfileName(name)
			setMode('active')
		} catch {
			// silent
		}
	}

	const handleSelectProfile = (name: string) => {
		loadProfileData(name, allBenchmarks)
	}

	const handleStartFresh = () => {
		setActiveMetrics([])
		setSelectedMetricKey(null)
		setProfileName('')
		setSourceProfileName(null)
		setMode('active')
		setTimeout(() => nameInputRef.current?.focus(), 50)
	}

	const handleReset = () => {
		setMode('landing')
		setActiveMetrics([])
		setSelectedMetricKey(null)
		setProfileName('')
		setSourceProfileName(null)
		setSaveStatus('idle')
		setOverwriteTarget(null)
	}

	const addMetric = (bench: Benchmark) => {
		if (activeKeys.has(bench.metric)) return
		const newMetric: StudioMetric = {
			metric: bench.metric,
			name: bench.name,
			asset_type: bench.asset_type,
			unit: bench.unit,
			is_decimal: bench.is_decimal,
			type: bench.type,
			best: bench.best,
			worst: bench.worst,
			target: bench.target,
			target_min: bench.target_min,
			target_max: bench.target_max,
			width: bench.width,
			threshold: bench.threshold,
			weight: 50,
			range_min: 0,
			range_max: 100,
			formula: bench.type,
		}
		setActiveMetrics(prev => [...prev, newMetric])
		setSelectedMetricKey(bench.metric)
	}

	const removeMetric = (key: string) => {
		setActiveMetrics(prev => prev.filter(m => m.metric !== key))
		if (selectedMetricKey === key) {
			const remaining = activeMetrics.filter(m => m.metric !== key)
			setSelectedMetricKey(remaining[0]?.metric ?? null)
		}
	}

	const updateMetric = (key: string, patch: Partial<StudioMetric>) => {
		setActiveMetrics(prev => prev.map(m => m.metric === key ? { ...m, ...patch } : m))
	}

	const doSave = async (name: string) => {
		if (saveStatus === 'saving') return
		setSaveStatus('saving')
		setOverwriteTarget(null)
		try {
			const weights: Record<string, number> = {}
			const ranges: Record<string, { min: number; max: number }> = {}
			const formulas: Record<string, string> = {}
			for (const m of activeMetrics) {
				weights[m.metric] = m.weight
				ranges[m.metric] = { min: m.range_min, max: m.range_max }
				formulas[m.metric] = m.formula
			}
			const res = await fetch(`${API_BASE_URL}/api/profiles`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name, weights, ranges, formulas }),
			})
			if (res.ok) {
				setSaveStatus('saved')
				setSourceProfileName(name)
				refetchProfiles()
			} else {
				setSaveStatus('error')
			}
		} catch {
			setSaveStatus('error')
		} finally {
			if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
			saveTimerRef.current = setTimeout(() => setSaveStatus('idle'), 2500)
		}
	}

	const handleSave = () => {
		const name = profileName.trim()
		if (!name) {
			nameInputRef.current?.focus()
			return
		}
		if (profileNameConflict) {
			setOverwriteTarget(name)
			return
		}
		doSave(name)
	}

	const saveBtnLabel = { idle: 'Save Profile', saving: 'Saving…', saved: 'Saved!', error: 'Error' }

	if (loading) return <div className="studio-drawer-loading">Loading Scoring Studio…</div>

	// Landing screen
	if (mode === 'landing' || mode === 'importing') {
		return (
			<div className="studio-landing">
				<div className="studio-landing-content">
					<h2 className="studio-landing-title">Scoring Studio</h2>
					<p className="studio-landing-desc">
						Configure how financial metrics are weighted and scored. Load an existing profile or build one from scratch.
					</p>

					{mode === 'landing' && (
						<div className="studio-start-cards">
							<button className="studio-start-card" onClick={() => setMode('importing')}>
								<Download size={28} />
								<span className="studio-start-card-title">Load a Profile</span>
								<span className="studio-start-card-desc">Import a system or saved profile to view and customize</span>
							</button>
							<button className="studio-start-card" onClick={handleStartFresh}>
								<Plus size={28} />
								<span className="studio-start-card-title">Start from Scratch</span>
								<span className="studio-start-card-desc">Build a new scoring profile with your own metrics and weights</span>
							</button>
						</div>
					)}

					{mode === 'importing' && (
						<div className="studio-import-picker">
							<div className="studio-import-header">
								<button className="studio-back-btn" onClick={() => setMode('landing')}>
									<ArrowLeft size={14} /> Back
								</button>
								<span className="studio-import-label">Select a profile to load</span>
							</div>
							<div className="studio-profile-list">
								{profileNames.length === 0 && (
									<p className="studio-no-profiles">No saved profiles found.</p>
								)}
								{profileNames.map(name => (
									<button
										key={name}
										className="studio-profile-item"
										onClick={() => handleSelectProfile(name)}
									>
										<span className="studio-profile-item-name">{name}</span>
										<Download size={14} className="studio-profile-item-icon" />
									</button>
								))}
							</div>
						</div>
					)}
				</div>
			</div>
		)
	}

	// Active mode
	// Pass the full metric (including any user-edited curve params) into the explorer
	const explorerSeed: Benchmark | undefined = selectedMetric
		? { ...selectedMetric, type: selectedMetric.formula as ScorerType }
		: undefined

	// Force ScoringExplorer to re-initialize when the selected metric changes
	const explorerKey = selectedMetricKey ?? 'none'

	return (
		<div className="studio-container">
			{/* Header */}
			<div className="studio-header">
				<button className="studio-back-btn" onClick={handleReset} title="Back to start">
					<ArrowLeft size={14} />
				</button>
				<div className="studio-name-group">
					<input
						ref={nameInputRef}
						className={`studio-name-input${profileNameConflict ? ' conflict' : ''}`}
						type="text"
						placeholder="Name this profile…"
						value={profileName}
						onChange={e => { setProfileName(e.target.value); setOverwriteTarget(null) }}
					/>
					{profileNameConflict && (
						<span className="studio-name-conflict">Will overwrite existing "{profileName.trim()}"</span>
					)}
				</div>
				<div className="studio-header-spacer" />
				{overwriteTarget ? (
					<div className="studio-overwrite-confirm">
						<span>Overwrite <strong>{overwriteTarget}</strong>?</span>
						<button className="studio-confirm-yes" onClick={() => doSave(overwriteTarget)}>Yes, overwrite</button>
						<button className="studio-confirm-no" onClick={() => setOverwriteTarget(null)}>Cancel</button>
					</div>
				) : (
					<button
						className={`studio-save-btn ${saveStatus}`}
						onClick={handleSave}
						disabled={saveStatus === 'saving' || !profileName.trim()}
					>
						{saveBtnLabel[saveStatus]}
					</button>
				)}
			</div>

			{/* Body */}
			<div className="studio-body">
				{/* Left — active set */}
				<div className="studio-left">
					<div className="studio-left-toolbar">
						<button className="studio-add-btn" onClick={() => setDrawerOpen(true)}>
							<Plus size={14} />
							Add from Library
						</button>
					</div>
					<div className="studio-metric-list">
						{activeMetrics.length === 0 && (
							<div className="studio-empty-set">
								No metrics yet.<br />Add some from the Library.
							</div>
						)}
						{activeMetrics.map(m => {
							const pct = totalWeight > 0 ? Math.round((m.weight / totalWeight) * 100) : 0
							return (
								<div
									key={m.metric}
									className={`studio-metric-row${selectedMetricKey === m.metric ? ' selected' : ''}`}
									onClick={() => setSelectedMetricKey(m.metric)}
								>
									<div className="studio-metric-left">
										<span className="studio-metric-name" title={m.name}>{m.name}</span>
										<div className="studio-metric-slider-row" onClick={e => e.stopPropagation()}>
											<input
												className="studio-importance-slider"
												type="range"
												min={0}
												max={100}
												step={1}
												value={m.weight}
												onChange={e => updateMetric(m.metric, { weight: parseInt(e.target.value) })}
											/>
											<span className="studio-contribution">{pct}%</span>
										</div>
									</div>
									<span className={`studio-formula-badge ${m.formula}`}>{FORMULA_LABELS[m.formula] ?? m.formula}</span>
									<button
										className="studio-remove-btn"
										title="Remove metric"
										onClick={e => { e.stopPropagation(); removeMetric(m.metric) }}
									>
										<X size={13} />
									</button>
								</div>
							)
						})}
					</div>
				</div>

				{/* Right — curve preview */}
				<div className="studio-right">
					{!selectedMetric ? (
						<div className="studio-curve-empty">
							<BookOpen size={36} />
							<p>Select a metric on the left to preview its scoring curve.</p>
						</div>
					) : (
						<div className="studio-curve-panel">
							<div className="studio-overrides">
								<div className="studio-override-group">
									<label>Importance — {totalWeight > 0 ? Math.round((selectedMetric.weight / totalWeight) * 100) : 0}% of score</label>
									<input
										type="range"
										min={0}
										max={100}
										step={1}
										value={selectedMetric.weight}
										onChange={e => updateMetric(selectedMetric.metric, { weight: parseInt(e.target.value) })}
									/>
								</div>
								<div className="studio-override-group">
									<label>Function</label>
									<select
										value={selectedMetric.formula}
										onChange={e => updateMetric(selectedMetric.metric, { formula: e.target.value, type: e.target.value as ScorerType })}
									>
										{availableFormulas.map(f => <option key={f} value={f}>{FORMULA_LABELS[f] ?? f}</option>)}
									</select>
								</div>

								{(selectedMetric.formula === 'sigmoid' || selectedMetric.formula === 'linear') && (<>
									<div className="studio-override-group">
										<label>Best Value</label>
										<input type="number" step="any"
											value={selectedMetric.best ?? ''}
											placeholder="e.g. 15"
											onChange={e => updateMetric(selectedMetric.metric, { best: parseNum(e.target.value) })}
										/>
									</div>
									<div className="studio-override-group">
										<label>Worst Value</label>
										<input type="number" step="any"
											value={selectedMetric.worst ?? ''}
											placeholder="e.g. 50"
											onChange={e => updateMetric(selectedMetric.metric, { worst: parseNum(e.target.value) })}
										/>
									</div>
								</>)}

								{selectedMetric.formula === 'bell_curve' && (<>
									<div className="studio-override-group">
										<label>Target</label>
										<input type="number" step="any"
											value={selectedMetric.target ?? ''}
											placeholder="e.g. 1.0"
											onChange={e => updateMetric(selectedMetric.metric, { target: parseNum(e.target.value) })}
										/>
									</div>
									<div className="studio-override-group">
										<label>Width (σ)</label>
										<input type="number" step="any" min={0.01}
											value={selectedMetric.width ?? ''}
											placeholder="e.g. 0.5"
											onChange={e => updateMetric(selectedMetric.metric, { width: parseNum(e.target.value) })}
										/>
									</div>
								</>)}

								{selectedMetric.formula === 'plateau' && (<>
									<div className="studio-override-group">
										<label>Target Min</label>
										<input type="number" step="any"
											value={selectedMetric.target_min ?? ''}
											onChange={e => updateMetric(selectedMetric.metric, { target_min: parseNum(e.target.value) })}
										/>
									</div>
									<div className="studio-override-group">
										<label>Target Max</label>
										<input type="number" step="any"
											value={selectedMetric.target_max ?? ''}
											onChange={e => updateMetric(selectedMetric.metric, { target_max: parseNum(e.target.value) })}
										/>
									</div>
									<div className="studio-override-group">
										<label>Decay Width</label>
										<input type="number" step="any" min={0.01}
											value={selectedMetric.width ?? ''}
											onChange={e => updateMetric(selectedMetric.metric, { width: parseNum(e.target.value) })}
										/>
									</div>
								</>)}

								{selectedMetric.formula === 'threshold' && (
									<div className="studio-override-group">
										<label>Threshold</label>
										<input type="number" step="any"
											value={selectedMetric.threshold ?? ''}
											onChange={e => updateMetric(selectedMetric.metric, { threshold: parseNum(e.target.value) })}
										/>
									</div>
								)}
							</div>
							<ScoringExplorer key={explorerKey} initialData={explorerSeed} />
						</div>
					)}
				</div>
			</div>

			{/* Library Drawer */}
			<div
				className={`studio-drawer-overlay${drawerOpen ? ' open' : ''}`}
				onClick={() => setDrawerOpen(false)}
			/>
			<div className={`studio-drawer${drawerOpen ? ' open' : ''}`}>
				<div className="studio-drawer-header">
					<h3>Metric Library</h3>
					<button className="studio-drawer-close" onClick={() => setDrawerOpen(false)}>
						<X size={14} />
					</button>
				</div>
				<div className="studio-drawer-filters">
					<div className="studio-drawer-search">
						<Search size={14} />
						<input
							type="text"
							placeholder="Search metrics…"
							value={drawerSearch}
							onChange={e => setDrawerSearch(e.target.value)}
						/>
					</div>
				</div>
				<div className="studio-library-scroll">
					<table className="studio-library-table">
						<thead>
							<tr>
								<th>Metric</th>
								<th>Type</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							{filteredDrawerBenchmarks.map(b => (
								<React.Fragment key={b.metric}>
									<tr className={`studio-library-row${drawerHistoryKey === b.metric ? ' history-open' : ''}`}>
										<td className="studio-lib-name">{b.name}</td>
										<td>
											<span className={`studio-formula-badge ${b.type}`}>{FORMULA_LABELS[b.type] ?? b.type}</span>
										</td>
										<td>
											<div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
												{activeKeys.has(b.metric) ? (
													<span className="studio-in-use-badge">In Use</span>
												) : (
													<button className="studio-lib-add-btn" onClick={() => addMetric(b)}>
														<Plus size={12} /> Add
													</button>
												)}
												<button
													className={`studio-lib-history-btn${drawerHistoryKey === b.metric ? ' active' : ''}`}
													title="View history"
													onClick={() => setDrawerHistoryKey(drawerHistoryKey === b.metric ? null : b.metric)}
												>
													<BarChart2 size={14} />
												</button>
											</div>
										</td>
									</tr>
									{drawerHistoryKey === b.metric && (
										<tr>
											<td colSpan={3} style={{ padding: 0 }}>
												<div className="studio-drawer-history">
													<MetricHistory metricKey={b.metric} metricName={b.name} />
												</div>
											</td>
										</tr>
									)}
								</React.Fragment>
							))}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	)
}

export default ScoringStudio
