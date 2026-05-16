import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Plus, X, Search, Filter, BarChart2, BookOpen } from 'lucide-react'
import { API_BASE_URL } from '../config'
import type { Benchmark, ScorerType } from '../types'
import type { StudioMetric } from '../types/studio'
import ScoringExplorer from './ScoringExplorer'
import MetricHistory from './MetricHistory'
import './ScoringStudio.css'

const FORMULA_LABELS: Record<string, string> = {
	sigmoid: 'Sigmoid',
	linear: 'Linear',
	bell_curve: 'Bell',
	plateau: 'Plateau',
	threshold: 'Thresh',
}

const ScoringStudio: React.FC = () => {
	const [allBenchmarks, setAllBenchmarks] = useState<Benchmark[]>([])
	const [sectors, setSectors] = useState<string[]>([])
	const [profileNames, setProfileNames] = useState<string[]>([])
	const [availableFormulas, setAvailableFormulas] = useState<string[]>([])
	const [loading, setLoading] = useState(true)

	const [activeMetrics, setActiveMetrics] = useState<StudioMetric[]>([])
	const [profileName, setProfileName] = useState('balanced')
	const [selectedMetricKey, setSelectedMetricKey] = useState<string | null>(null)

	const [drawerOpen, setDrawerOpen] = useState(false)
	const [drawerSearch, setDrawerSearch] = useState('')
	const [drawerSector, setDrawerSector] = useState('')
	const [drawerBenchmarks, setDrawerBenchmarks] = useState<Benchmark[]>([])
	const [drawerHistoryKey, setDrawerHistoryKey] = useState<string | null>(null)

	const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

	const profileLoadRef = useRef(0)
	const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

	const selectedMetric = useMemo(
		() => activeMetrics.find(m => m.metric === selectedMetricKey) ?? null,
		[activeMetrics, selectedMetricKey]
	)

	const activeKeys = useMemo(() => new Set(activeMetrics.map(m => m.metric)), [activeMetrics])

	const filteredDrawerBenchmarks = useMemo(() => {
		const q = drawerSearch.toLowerCase()
		if (!q) return drawerBenchmarks
		return drawerBenchmarks.filter(
			b => b.name.toLowerCase().includes(q) || b.metric.toLowerCase().includes(q)
		)
	}, [drawerBenchmarks, drawerSearch])

	useEffect(() => {
		const init = async () => {
			setLoading(true)
			try {
				const [benchRes, sectorRes, profileListRes, formulaRes] = await Promise.all([
					fetch(`${API_BASE_URL}/api/benchmarks?asset_type=STOCK`),
					fetch(`${API_BASE_URL}/api/sectors`),
					fetch(`${API_BASE_URL}/api/profiles/list`),
					fetch(`${API_BASE_URL}/api/formulas`),
				])
				const benchmarks: Benchmark[] = benchRes.ok ? await benchRes.json() : []
				const sectorList: string[] = sectorRes.ok ? await sectorRes.json() : []
				const names: string[] = profileListRes.ok ? await profileListRes.json() : []
				const formulas: string[] = formulaRes.ok ? await formulaRes.json() : []

				setAllBenchmarks(benchmarks)
				setDrawerBenchmarks(benchmarks)
				setSectors(sectorList)
				setProfileNames(names)
				setAvailableFormulas(formulas)

				const defaultProfile = names[0] ?? 'balanced'
				setProfileName(defaultProfile)
				await loadProfileWithBenchmarks(defaultProfile, benchmarks)
			} finally {
				setLoading(false)
			}
		}
		init()
	}, [])

	useEffect(() => {
		if (!drawerOpen) return
		const fetchSectorBenchmarks = async () => {
			const sectorParam = drawerSector ? `&sector=${encodeURIComponent(drawerSector)}` : ''
			const res = await fetch(`${API_BASE_URL}/api/benchmarks?asset_type=STOCK${sectorParam}`)
			if (res.ok) setDrawerBenchmarks(await res.json())
		}
		fetchSectorBenchmarks()
	}, [drawerSector, drawerOpen])

	const loadProfileWithBenchmarks = async (name: string, benchmarks: Benchmark[]) => {
		const requestId = ++profileLoadRef.current
		try {
			const res = await fetch(`${API_BASE_URL}/api/profiles/${encodeURIComponent(name)}`)
			if (!res.ok) return
			const profile: { name: string; weights: Record<string, number>; ranges: Record<string, { min: number; max: number }>; formulas: Record<string, string> } = await res.json()
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
		} catch {
			// silent — backend may be offline
		}
	}

	const loadProfile = async (name: string) => {
		setProfileName(name)
		await loadProfileWithBenchmarks(name, allBenchmarks)
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
			weight: 1.0,
			range_min: 0,
			range_max: 100,
			formula: bench.type,
		}
		setActiveMetrics(prev => [...prev, newMetric])
		setSelectedMetricKey(bench.metric)
		setDrawerOpen(false)
	}

	const removeMetric = (key: string) => {
		setActiveMetrics(prev => prev.filter(m => m.metric !== key))
		if (selectedMetricKey === key) {
			setSelectedMetricKey(prev => {
				const remaining = activeMetrics.filter(m => m.metric !== key)
				return remaining[0]?.metric ?? null
			})
		}
	}

	const updateMetric = (key: string, patch: Partial<StudioMetric>) => {
		setActiveMetrics(prev => prev.map(m => m.metric === key ? { ...m, ...patch } : m))
	}

	const saveProfile = async () => {
		if (saveStatus === 'saving') return
		setSaveStatus('saving')
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
				body: JSON.stringify({ name: profileName, weights, ranges, formulas }),
			})
			setSaveStatus(res.ok ? 'saved' : 'error')
		} catch {
			setSaveStatus('error')
		} finally {
			if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
			saveTimerRef.current = setTimeout(() => setSaveStatus('idle'), 2500)
		}
	}

	const saveBtnLabel = { idle: 'Save Profile', saving: 'Saving…', saved: 'Saved!', error: 'Error' }

	if (loading) return <div className="studio-drawer-loading">Loading Scoring Studio…</div>

	const explorerSeed: Benchmark | undefined = selectedMetric
		? { ...selectedMetric, type: selectedMetric.formula as ScorerType }
		: undefined

	return (
		<div className="studio-container">
			{/* Header */}
			<div className="studio-header">
				<span className="studio-header-title">Studio</span>
				<select
					className="studio-profile-select"
					value={profileName}
					onChange={e => loadProfile(e.target.value)}
				>
					{profileNames.map(n => <option key={n} value={n}>{n}</option>)}
				</select>
				<input
					className="studio-name-input"
					type="text"
					placeholder="Profile name…"
					value={profileName}
					onChange={e => setProfileName(e.target.value)}
				/>
				<div className="studio-header-spacer" />
				<button
					className={`studio-save-btn ${saveStatus}`}
					onClick={saveProfile}
					disabled={saveStatus === 'saving'}
				>
					{saveBtnLabel[saveStatus]}
				</button>
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
								No metrics yet. Add some from the Library.
							</div>
						)}
						{activeMetrics.map(m => (
							<div
								key={m.metric}
								className={`studio-metric-row${selectedMetricKey === m.metric ? ' selected' : ''}`}
								onClick={() => setSelectedMetricKey(m.metric)}
							>
								<span className="studio-metric-name" title={m.name}>{m.name}</span>
								<input
									className="studio-weight-input"
									type="number"
									min={0}
									max={5}
									step={0.1}
									value={m.weight}
									onClick={e => e.stopPropagation()}
									onChange={e => updateMetric(m.metric, { weight: parseFloat(e.target.value) || 0 })}
								/>
								<span className="studio-weight-unit">×</span>
								<span className={`studio-formula-badge ${m.formula}`}>{FORMULA_LABELS[m.formula] ?? m.formula}</span>
								<button
									className="studio-remove-btn"
									title="Remove metric"
									onClick={e => { e.stopPropagation(); removeMetric(m.metric) }}
								>
									<X size={13} />
								</button>
							</div>
						))}
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
									<label>Weight (×)</label>
									<input
										type="number"
										min={0}
										max={5}
										step={0.1}
										value={selectedMetric.weight}
										onChange={e => updateMetric(selectedMetric.metric, { weight: parseFloat(e.target.value) || 0 })}
									/>
								</div>
								<div className="studio-override-group">
									<label>Formula</label>
									<select
										value={selectedMetric.formula}
										onChange={e => updateMetric(selectedMetric.metric, { formula: e.target.value })}
									>
										{availableFormulas.map(f => <option key={f} value={f}>{f}</option>)}
									</select>
								</div>
								<div className="studio-override-group">
									<label>Range Min</label>
									<input
										type="number"
										value={selectedMetric.range_min}
										onChange={e => updateMetric(selectedMetric.metric, { range_min: parseFloat(e.target.value) || 0 })}
									/>
								</div>
								<div className="studio-override-group">
									<label>Range Max</label>
									<input
										type="number"
										value={selectedMetric.range_max}
										onChange={e => updateMetric(selectedMetric.metric, { range_max: parseFloat(e.target.value) || 0 })}
									/>
								</div>
							</div>
							<ScoringExplorer initialData={explorerSeed} />
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
					<div className="studio-drawer-sector">
						<Filter size={14} />
						<select value={drawerSector} onChange={e => { setDrawerSector(e.target.value); setDrawerHistoryKey(null) }}>
							<option value="">Global</option>
							{sectors.map(s => <option key={s} value={s}>{s}</option>)}
						</select>
					</div>
				</div>
				<div className="studio-library-scroll">
					<table className="studio-library-table">
						<thead>
							<tr>
								<th>Metric</th>
								<th>Type</th>
								<th>Weight</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							{filteredDrawerBenchmarks.map(b => (
								<React.Fragment key={b.metric}>
									<tr
										className={`studio-library-row${drawerHistoryKey === b.metric ? ' history-open' : ''}`}
									>
										<td className="studio-lib-name">{b.name}</td>
										<td>
											<span className={`studio-formula-badge ${b.type}`}>{FORMULA_LABELS[b.type] ?? b.type}</span>
										</td>
										<td>{b.weight.toFixed(1)}×</td>
										<td>
											<div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
												{activeKeys.has(b.metric) ? (
													<span className="studio-in-use-badge">In Use</span>
												) : (
													<button
														className="studio-lib-add-btn"
														onClick={() => addMetric(b)}
													>
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
											<td colSpan={4} style={{ padding: 0 }}>
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
