import React, { useMemo, useState } from 'react'
import {
	createColumnHelper,
	flexRender,
	getCoreRowModel,
	useReactTable,
	getSortedRowModel,
	getFilteredRowModel,
} from '@tanstack/react-table'
import type { SortingState, VisibilityState } from '@tanstack/react-table'
import type { AssetAnalysis } from '../types'
import { ChevronDown, ChevronUp, Settings2, Search } from 'lucide-react'
import './ResultsGrid.css'

interface ResultsGridProps {
	data: AssetAnalysis[]
}

const columnHelper = createColumnHelper<AssetAnalysis>()

const ResultsGrid: React.FC<ResultsGridProps> = ({ data }) => {
	const [sorting, setSorting] = useState<SortingState>([{ id: 'score', desc: true }])
	const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
	const [globalFilter, setGlobalFilter] = useState('')
	const [showSettings, setShowSettings] = useState(false)

	// 1. Identify all unique metrics across all assets to build dynamic columns
	const allMetrics = useMemo(() => {
		const metrics = new Map<string, string>()
		data.forEach(asset => {
			asset.results.forEach(m => {
				if (!metrics.has(m.metric)) {
					metrics.set(m.metric, m.name)
				}
			})
		})
		return Array.from(metrics.entries()).map(([key, name]) => ({ key, name }))
	}, [data])

	// 2. Define Columns
	const columns = useMemo(() => {
		const baseColumns = [
			columnHelper.accessor('symbol', {
				header: 'Symbol',
				cell: info => <span className="symbol-cell">{info.getValue()}</span>,
			}),
			columnHelper.accessor('name', {
				header: 'Name',
				cell: info => <span className="name-cell">{info.getValue()}</span>,
			}),
			columnHelper.accessor('score', {
				header: 'Total Score',
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
				header: `${m.name} (Val)`,
				cell: info => <span className="metric-value">{info.getValue() ?? 'N/A'}</span>,
			}),
			columnHelper.accessor(row => row.results.find(r => r.metric === m.key)?.status, {
				id: `${m.key}_strength`,
				header: `${m.name} (%)`,
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
			globalFilter,
		},
		onSortingChange: setSorting,
		onColumnVisibilityChange: setColumnVisibility,
		onGlobalFilterChange: setGlobalFilter,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getFilteredRowModel: getFilteredRowModel(),
	})

	if (data.length === 0) {
		return (
			<div className="empty-state">
				<p className="empty-text">No analysis results to display. Run an analysis to see scores here.</p>
			</div>
		)
	}

	return (
		<div className="results-grid-container">
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
			</div>

			{showSettings && (
				<div className="column-settings">
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

			<div className="table-wrapper">
				<table className="results-table">
					<thead>
						{table.getHeaderGroups().map(headerGroup => (
							<tr key={headerGroup.id}>
								{headerGroup.headers.map(header => (
									<th 
										key={header.id} 
										className={header.column.getCanSort() ? 'sortable' : ''}
										onClick={header.column.getToggleSortingHandler()}
									>
										<div className="header-content">
											{flexRender(header.column.columnDef.header, header.getContext())}
											{{
												asc: <ChevronUp size={14} className="status-high" />,
												desc: <ChevronDown size={14} className="status-high" />,
											}[header.column.getIsSorted() as string] ?? null}
										</div>
									</th>
								))}
							</tr>
						))}
					</thead>
					<tbody>
						{table.getRowModel().rows.map(row => (
							<tr key={row.id}>
								{row.getVisibleCells().map(cell => (
									<td key={cell.id}>
										{flexRender(cell.column.columnDef.cell, cell.getContext())}
									</td>
								))}
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	)
}


export default ResultsGrid

