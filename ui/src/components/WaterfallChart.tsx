import React, { useMemo } from 'react'
import {
	ComposedChart,
	Bar,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	Cell,
	ResponsiveContainer,
	LabelList,
} from 'recharts'
import type { MetricResult } from '../types'
import './WaterfallChart.css'

interface WaterfallChartProps {
	results: MetricResult[]
	totalScore: number
}

interface WaterfallEntry {
	name: string
	spacer: number
	value: number
	contribution: number
	rawDisplay: unknown
	status: string
	isTotal: boolean
}

function barColor(entry: WaterfallEntry): string {
	if (entry.isTotal) return '#3b82f6'
	const c = entry.contribution
	if (c >= 7) return '#22c55e'
	if (c >= 3) return '#86efac'
	if (c >= 1) return '#fbbf24'
	return '#6b7280'
}

interface TooltipProps {
	active?: boolean
	payload?: Array<{ payload: WaterfallEntry }>
}

const CustomTooltip: React.FC<TooltipProps> = ({ active, payload }) => {
	if (!active || !payload?.length) return null
	const d = payload[0].payload
	return (
		<div className="wf-tooltip">
			<div className="wf-tooltip-name">{d.name}</div>
			{!d.isTotal && (
				<>
					<div className="wf-tooltip-row">
						<span>Value</span>
						<span>{d.rawDisplay != null ? String(d.rawDisplay) : '—'}</span>
					</div>
					<div className="wf-tooltip-row">
						<span>Strength</span>
						<span>{d.status}</span>
					</div>
				</>
			)}
			<div className="wf-tooltip-row wf-tooltip-contrib">
				<span>{d.isTotal ? 'Final Score' : 'Contribution'}</span>
				<span>{d.isTotal ? d.contribution.toFixed(1) : `+${d.contribution.toFixed(1)}`}</span>
			</div>
		</div>
	)
}

const WaterfallChart: React.FC<WaterfallChartProps> = ({ results, totalScore }) => {
	const data = useMemo<WaterfallEntry[]>(() => {
		const totalWeight = results.reduce((sum, r) => sum + r.weight, 0)

		const sorted = [...results]
			.map(r => ({
				...r,
				contribution: totalWeight > 0 ? (r.score / totalWeight) * 100 : 0,
			}))
			.sort((a, b) => b.contribution - a.contribution)

		let cumulative = 0
		const bars: WaterfallEntry[] = sorted.map(r => {
			const entry: WaterfallEntry = {
				name: r.name,
				spacer: cumulative,
				value: r.contribution,
				contribution: r.contribution,
				rawDisplay: r.value,
				status: r.status,
				isTotal: false,
			}
			cumulative += r.contribution
			return entry
		})

		bars.push({
			name: 'Total',
			spacer: 0,
			value: totalScore,
			contribution: totalScore,
			rawDisplay: null,
			status: `${totalScore.toFixed(1)}%`,
			isTotal: true,
		})

		return bars
	}, [results, totalScore])

	return (
		<ResponsiveContainer width="100%" height={420}>
			<ComposedChart data={data} margin={{ top: 24, right: 16, bottom: 64, left: 16 }}>
				<CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
				<XAxis
					dataKey="name"
					tick={{ fill: '#9ca3af', fontSize: 11 }}
					angle={-38}
					textAnchor="end"
					interval={0}
					tickLine={false}
					axisLine={{ stroke: '#374151' }}
				/>
				<YAxis
					domain={[0, 100]}
					tick={{ fill: '#9ca3af', fontSize: 11 }}
					tickLine={false}
					axisLine={false}
					width={32}
				/>
				<Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
				{/* transparent spacer creates the floating-bar waterfall effect */}
				<Bar dataKey="spacer" stackId="wf" fill="transparent" isAnimationActive={false} />
				<Bar dataKey="value" stackId="wf" radius={[3, 3, 0, 0]}>
					{data.map((entry, idx) => (
						<Cell key={idx} fill={barColor(entry)} />
					))}
					<LabelList
						dataKey="value"
						position="top"
						formatter={(v: unknown) => {
							const n = typeof v === 'number' ? v : 0
							if (n < 1) return ''
							const entry = data.find(d => d.value === n)
							return entry?.isTotal ? `${n.toFixed(1)}` : `+${n.toFixed(1)}`
						}}
						style={{ fill: '#9ca3af', fontSize: 10 }}
					/>
				</Bar>
			</ComposedChart>
		</ResponsiveContainer>
	)
}

export default WaterfallChart
