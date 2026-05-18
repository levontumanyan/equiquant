import React, { useMemo, useState, useEffect, useCallback, useRef } from 'react'
import {
	createColumnHelper,
	flexRender,
	getCoreRowModel,
	useReactTable,
	getSortedRowModel,
	getFilteredRowModel,
} from '@tanstack/react-table'
import type { ColumnSizingState, SortingState, VisibilityState } from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import type { AssetAnalysis } from '../types'
import { ChevronDown, ChevronUp, Settings2, Search, Maximize2, Minimize2 } from 'lucide-react'
import { API_BASE_URL } from '../config'
import RawMetricsDrawer from './RawMetricsDrawer'
import './ResultsGrid.css'

interface ResultsGridProps {
	data: AssetAnalysis[]
	profile?: string
	externalFilter?: string
}

interface ProfileData {
	name: string
	weights: Record<string, number>
}

const columnHelper = createColumnHelper<AssetAnalysis>()

const COL_SIZES = {
	symbol: 75,
	name: 140,
	score: 130,
	metricPct: 58,
}

// Estimate column width from header text — mimics Excel autofit for metric columns.
// ~7px per char at 0.75rem uppercase + 24px padding, capped at 160.
const metricValSize = (name: string) => Math.min(Math.max(name.length * 7 + 24, 70), 160)

const ResultsGrid: React.FC<ResultsGridProps> = ({ data, profile, externalFilter }) => {
	const [sorting, setSorting] = useState<SortingState>([{ id: 'score', desc: true }])
	const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
	const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({})
	const [globalFilter, setGlobalFilter] = useState(externalFilter ?? '')

	useEffect(() => {
		if (externalFilter !== undefined) setGlobalFilter(externalFilter)
	}, [externalFilter])
	const [showSettings, setShowSettings] = useState(false)
	const [fullscreen, setFullscreen] = useState(false)
	const [profileMetricKeys, setProfileMetricKeys] = useState<string[]>([])
	const [profileFilterActive, setProfileFilterActive] = useState(false)
	const [preset, setPreset] = useState<'all' | 'none' | 'values' | 'strength'>('all')
	const [selectedAsset, setSelectedAsset] = useState<AssetAnalysis | null>(null)

	const tableContainerRef = useRef<HTMLDivElement>(null)

	// Refs mirror the corresponding state so effects can read current values without
	// being listed as dependencies (avoids re-running effects on every render).
	const presetRef = useRef<typeof preset>('all')
	const profileFilterActiveRef = useRef(true)
	const profileMetricKeysRef = useRef<string[]>([])

	// Apply a column preset imperatively — avoids a reactive effect that would
	// overwrite per-metric checkbox state whenever profileMetricKeys loads.
	const applyPreset = useCallback((
		nextPreset: typeof preset,
		nextProfileActive: boolean,
		metrics: typeof allMetrics,
		profileKeys: string[],
	) => {
		const showValues   = nextPreset !== 'strength' && nextPreset !== 'none'
		const showStrength = nextPreset !== 'values'   && nextPreset !== 'none'
		const next: VisibilityState = {}
		metrics.forEach(m => {
			const inProfile = !nextProfileActive || profileKeys.includes(m.key)
			next[`${m.key}_value`]    = inProfile && showValues
			next[`${m.key}_strength`] = inProfile && showStrength
		})
		setColumnVisibility(next)
	}, [])

	useEffect(() => {
		if (!profile) return
		const controller = new AbortController()
		profileFilterActiveRef.current = true
		setProfileFilterActive(true)
		fetch(`${API_BASE_URL}/api/profiles/${encodeURIComponent(profile)}`, { signal: controller.signal })
			.then(r => r.ok ? r.json() : null)
			.then((p: ProfileData | null) => {
				const keys = p ? Object.keys(p.weights) : []
				profileMetricKeysRef.current = keys
				setProfileMetricKeys(keys)
				// If metrics are already present (e.g. re-selecting profile), apply filter now.
				if (allMetrics.length > 0) {
					applyPreset(presetRef.current, true, allMetrics, keys)
				}
			})
			.catch(err => { if (err.name !== 'AbortError') setProfileMetricKeys([]) })
		return () => controller.abort()
	}, [profile])

	// 1. Identify all unique metrics across all assets to build dynamic columns.
	// Stored in a ref so the Map survives re-renders without triggering effects;
	// allMetrics state (and thus columns) only updates when a genuinely new metric key arrives.
	const metricsMapRef = useRef<Map<string, string>>(new Map())
	const [allMetrics, setAllMetrics] = useState<{ key: string; name: string }[]>([])

	useEffect(() => {
		let changed = false
		data.forEach(asset => {
			asset.results.forEach(m => {
				if (!metricsMapRef.current.has(m.metric)) {
					metricsMapRef.current.set(m.metric, m.name)
					changed = true
				}
			})
		})
		if (changed) {
			const newMetrics = Array.from(metricsMapRef.current.entries()).map(([key, name]) => ({ key, name }))
			setAllMetrics(newMetrics)
			// Keep non-profile metrics hidden as they stream in while the filter is active.
			if (profileFilterActiveRef.current && profileMetricKeysRef.current.length > 0) {
				applyPreset(presetRef.current, true, newMetrics, profileMetricKeysRef.current)
			}
		}
	}, [data])


	// 2. Define Columns
	const columns = useMemo(() => {
		const baseColumns = [
			columnHelper.accessor('symbol', {
				header: 'Symbol',
				size: COL_SIZES.symbol,
				cell: info => <span className="symbol-cell">{info.getValue()}</span>,
			}),
			columnHelper.accessor('name', {
				header: 'Name',
				size: COL_SIZES.name,
				cell: info => <span className="name-cell" title={info.getValue()}>{info.getValue()}</span>,
			}),
			columnHelper.accessor('score', {
				header: 'Score',
				size: COL_SIZES.score,
				cell: info => {
					const score = info.getValue()
					const statusClass = score >= 70 ? "bg-high" : score >= 40 ? "bg-medium" : "bg-low"
					const textClass = score >= 70 ? "status-high" : score >= 40 ? "status-medium" : "status-low"
					
					return (
						<div className="score-container">
							<div className="score-bar-bg">
								<div 
									className={`score-bar-fill ${statusClass}`}
									style={{ width: `${score}%` }}
								/>
							</div>
							<span className={`score-text ${textClass}`}>
								{score.toFixed(1)}%
							</span>
						</div>
					)
				},
			}),
		]

		const metricColumns = allMetrics.flatMap(m => [
			columnHelper.accessor(row => row.results.find(r => r.metric === m.key)?.value, {
				id: `${m.key}_value`,
				header: m.name,
				size: metricValSize(m.name),
				cell: info => <span className="metric-value">{info.getValue() ?? 'N/A'}</span>,
			}),
			columnHelper.accessor(row => row.results.find(r => r.metric === m.key)?.status, {
				id: `${m.key}_strength`,
				header: '%',
				size: COL_SIZES.metricPct,
				cell: info => {
					const status = info.getValue()
					if (!status) return <span className="metric-value">N/A</span>
					const val = parseFloat(status.replace('%', ''))
					const statusClass = val >= 70 ? "status-high" : val >= 40 ? "status-medium" : "status-low"
					return (
						<span className={`metric-strength ${statusClass}`}>
							{status}
						</span>
					)
				},
			}),
		])

		return [...baseColumns, ...metricColumns]
	}, [allMetrics])

	const table = useReactTable({
		data,
		columns,
		state: {
			sorting,
			columnVisibility,
			columnSizing,
			globalFilter,
		},
		columnResizeMode: 'onChange',
		onSortingChange: setSorting,
		onColumnVisibilityChange: setColumnVisibility,
		onColumnSizingChange: setColumnSizing,
		onGlobalFilterChange: setGlobalFilter,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getFilteredRowModel: getFilteredRowModel(),
	})

	const { rows } = table.getRowModel()

	const rowVirtualizer = useVirtualizer({
		count: rows.length,
		getScrollElement: () => tableContainerRef.current,
		estimateSize: () => 45, // Estimated row height in pixels
		overscan: 10,
	})

	if (data.length === 0) {
		return (
			<div className="empty-state">
				<p className="empty-text">No analysis results to display. Run an analysis to see scores here.</p>
			</div>
		)
	}

	const virtualRows = rowVirtualizer.getVirtualItems()
	const totalSize = rowVirtualizer.getTotalSize()
	const paddingTop = virtualRows.length > 0 ? virtualRows[0].start : 0
	const paddingBottom = virtualRows.length > 0 ? totalSize - virtualRows[virtualRows.length - 1].end : 0
	return (
		<>
		<div className={`results-grid-container${fullscreen ? ' fullscreen' : ''}`}>
			<div className="results-grid-header">
				<div className="header-left">
					<h3 className="results-grid-title">
						Analysis Results 
						<span className="asset-count-badge">
							{data.length} assets
						</span>
					</h3>
					<div className="search-container">
						<Search size={14} className="search-icon" />
						<input
							type="text"
							value={globalFilter ?? ''}
							onChange={e => setGlobalFilter(e.target.value)}
							placeholder="Search assets..."
							className="search-input"
						/>
					</div>
				</div>
				
				<button
					onClick={() => setShowSettings(!showSettings)}
					className={`settings-button ${showSettings ? 'active' : ''}`}
				>
					<Settings2 size={16} />
					Columns
				</button>
				<button
					onClick={() => setFullscreen(f => !f)}
					className="settings-button"
					title={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
				>
					{fullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
				</button>
			</div>

			{showSettings && (
				<div className="column-settings">
					<div className="col-settings-actions">
						<button
							className={`col-action-btn${preset === 'all' && !profileFilterActive ? ' col-action-btn--on' : ''}`}
							onClick={() => {
								presetRef.current = 'all'
								profileFilterActiveRef.current = false
								setPreset('all')
								setProfileFilterActive(false)
								applyPreset('all', false, allMetrics, profileMetricKeys)
							}}
						>
							Select All
						</button>
						<button
							className={`col-action-btn${preset === 'none' ? ' col-action-btn--on' : ''}`}
							onClick={() => {
								presetRef.current = 'none'
								profileFilterActiveRef.current = false
								setPreset('none')
								setProfileFilterActive(false)
								applyPreset('none', false, allMetrics, profileMetricKeys)
							}}
						>
							Select None
						</button>
						<button
							className={`col-action-btn${preset === 'values' ? ' col-action-btn--on' : ''}`}
							onClick={() => {
								presetRef.current = 'values'
								setPreset('values')
								applyPreset('values', profileFilterActive, allMetrics, profileMetricKeys)
							}}
							title="Show metric values, hide strength scores"
						>
							Values
						</button>
						<button
							className={`col-action-btn${preset === 'strength' ? ' col-action-btn--on' : ''}`}
							onClick={() => {
								presetRef.current = 'strength'
								setPreset('strength')
								applyPreset('strength', profileFilterActive, allMetrics, profileMetricKeys)
							}}
							title="Show strength scores only"
						>
							Strength
						</button>
						{profileMetricKeys.length > 0 && (
							<button
								className={`col-action-btn col-action-btn--profile${profileFilterActive ? ' col-action-btn--on' : ''}`}
								onClick={() => {
									const next = !profileFilterActive
									profileFilterActiveRef.current = next
									setProfileFilterActive(next)
									applyPreset(preset, next, allMetrics, profileMetricKeys)
								}}
								title={`Filter to metrics in the "${profile}" profile`}
							>
								{profile}
							</button>
						)}
						<span className="col-action-count">
							{allMetrics.filter(m =>
								table.getColumn(`${m.key}_value`)?.getIsVisible() ||
								table.getColumn(`${m.key}_strength`)?.getIsVisible()
							).length} / {allMetrics.length} shown
						</span>
					</div>
					<div className="col-settings-divider" />
					<div className="settings-grid">
						{allMetrics.map(m => (
							<div key={m.key} className="metric-setting-group">
								<span className="metric-setting-name" title={m.name}>{m.name}</span>
								
								<div className="setting-controls">
									<label className="setting-sub-item">
										<input
											type="checkbox"
											checked={table.getColumn(`${m.key}_value`)?.getIsVisible()}
											onChange={table.getColumn(`${m.key}_value`)?.getToggleVisibilityHandler()}
										/>
										<span>Value</span>
									</label>

									<label className="setting-sub-item">
										<input
											type="checkbox"
											checked={table.getColumn(`${m.key}_strength`)?.getIsVisible()}
											onChange={table.getColumn(`${m.key}_strength`)?.getToggleVisibilityHandler()}
										/>
										<span>Strength</span>
									</label>
								</div>
							</div>
						))}
					</div>
				</div>
			)}

			<div className="table-wrapper" ref={tableContainerRef}>
				<table
					className="results-table"
					style={{ width: table.getTotalSize(), tableLayout: 'fixed' }}
				>
					<thead>
						{table.getHeaderGroups().map(headerGroup => (
							<tr key={headerGroup.id}>
								{headerGroup.headers.map(header => (
									<th
										key={header.id}
										style={{ width: header.getSize() }}
									>
										<div
											className={`header-content${header.column.getCanSort() ? ' sortable' : ''}`}
											onClick={header.column.getToggleSortingHandler()}
										>
											{flexRender(header.column.columnDef.header, header.getContext())}
											{{
												asc: <ChevronUp size={14} className="status-high" />,
												desc: <ChevronDown size={14} className="status-high" />,
											}[header.column.getIsSorted() as string] ?? null}
										</div>
										<div
											className={`resize-handle${header.column.getIsResizing() ? ' resizing' : ''}`}
											onMouseDown={e => { e.stopPropagation(); header.getResizeHandler()(e) }}
											onTouchStart={e => { e.stopPropagation(); header.getResizeHandler()(e) }}
											onClick={e => e.stopPropagation()}
										/>
									</th>
								))}
							</tr>
						))}
					</thead>
					<tbody>
						{paddingTop > 0 && (
							<tr>
								<td 
									colSpan={table.getVisibleFlatColumns().length} 
									style={{ height: `${paddingTop}px` }} 
								/>
							</tr>
						)}
						{virtualRows.map(virtualRow => {
							const row = rows[virtualRow.index]
							return (
								<tr
									key={row.id}
									className={`clickable-row${selectedAsset?.symbol === row.original.symbol ? ' row-selected' : ''}`}
									onClick={() => setSelectedAsset(prev =>
										prev?.symbol === row.original.symbol ? null : row.original
									)}
									title="Click to view raw provider data"
								>
									{row.getVisibleCells().map(cell => (
										<td key={cell.id}>
											{flexRender(cell.column.columnDef.cell, cell.getContext())}
										</td>
									))}
								</tr>
							)
						})}
						{paddingBottom > 0 && (
							<tr>
								<td 
									colSpan={table.getVisibleFlatColumns().length} 
									style={{ height: `${paddingBottom}px` }} 
								/>
							</tr>
						)}
					</tbody>
				</table>
			</div>
		</div>

		<RawMetricsDrawer
			asset={selectedAsset}
			onClose={() => setSelectedAsset(null)}
		/>
		</>
	)
}


export default ResultsGrid
