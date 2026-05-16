import { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import * as d3 from 'd3'
import { Maximize2, Minimize2 } from 'lucide-react'
import type { AssetAnalysis } from '../types'
import './SmartHeatmap.css'

interface SmartHeatmapProps {
	data: AssetAnalysis[]
	onSelectSymbol?: (symbol: string) => void
}

interface LeafNode {
	symbol: string
	name: string
	sector: string | null
	industry: string | null
	score: number
	market_cap: number | null
	x0: number
	y0: number
	x1: number
	y1: number
}

interface Tooltip {
	clientX: number
	clientY: number
	leaf: LeafNode
}

function scoreToColor(score: number): string {
	const s = Math.max(0, Math.min(100, score))
	if (s <= 50) return d3.interpolateRgb('#ef4444', '#eab308')(s / 50)
	return d3.interpolateRgb('#eab308', '#22c55e')((s - 50) / 50)
}

function formatMarketCap(n: number | null | undefined): string {
	if (n == null) return 'N/A'
	if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
	if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
	if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`
	return `$${n.toFixed(0)}`
}

interface HierarchyLeaf {
	symbol: string
	name: string
	sector: string | null
	industry: string | null
	score: number
	market_cap: number | null
	value: number
}

const SmartHeatmap: React.FC<SmartHeatmapProps> = ({ data, onSelectSymbol }) => {
	const containerRef = useRef<HTMLDivElement>(null)
	const canvasRef = useRef<HTMLCanvasElement>(null)
	const [equalWeight, setEqualWeight] = useState(false)
	const [fullscreen, setFullscreen] = useState(false)
	const [tooltip, setTooltip] = useState<Tooltip | null>(null)
	const [hovering, setHovering] = useState(false)
	const leafNodesRef = useRef<LeafNode[]>([])

	const hierarchyData = useMemo(() => {
		const sectorMap = new Map<string, Map<string, HierarchyLeaf[]>>()
		for (const a of data) {
			const sector = a.sector ?? 'Unknown'
			const industry = a.industry ?? 'Other'
			if (!sectorMap.has(sector)) sectorMap.set(sector, new Map())
			const ind = sectorMap.get(sector)!
			if (!ind.has(industry)) ind.set(industry, [])
			ind.get(industry)!.push({
				symbol: a.symbol,
				name: a.name,
				sector: a.sector,
				industry: a.industry,
				score: a.score,
				market_cap: a.market_cap ?? null,
				value: equalWeight ? 1 : Math.max(a.market_cap ?? 0, 1),
			})
		}
		return {
			name: 'root',
			children: [...sectorMap.entries()].map(([sector, industries]) => ({
				name: sector,
				children: [...industries.entries()].map(([industry, leaves]) => ({
					name: industry,
					children: leaves,
				})),
			})),
		}
	}, [data, equalWeight])

	const draw = useCallback((width: number, height: number) => {
		const canvas = canvasRef.current
		if (!canvas || width < 4 || height < 4) return

		const dpr = window.devicePixelRatio || 1
		canvas.width = Math.round(width * dpr)
		canvas.height = Math.round(height * dpr)
		canvas.style.width = `${width}px`
		canvas.style.height = `${height}px`

		const ctx = canvas.getContext('2d')!
		ctx.scale(dpr, dpr)
		ctx.clearRect(0, 0, width, height)

		const root = d3
			.hierarchy<any>(hierarchyData)
			.sum((d) => d.value ?? 0)
			.sort((a, b) => (b.value ?? 0) - (a.value ?? 0))

		d3.treemap<any>()
			.size([width, height])
			.paddingOuter(3)
			.paddingInner(1)
			.paddingTop(18)
			.round(true)(root)

		const leaves: LeafNode[] = []

		// Sector label backgrounds (depth 1)
		for (const sectorNode of root.children ?? []) {
			const { x0, y0, x1, y1 } = sectorNode as any
			ctx.fillStyle = 'rgba(255,255,255,0.03)'
			ctx.fillRect(x0, y0, x1 - x0, y1 - y0)
			ctx.fillStyle = 'rgba(255,255,255,0.28)'
			ctx.font = '9px Inter, system-ui, sans-serif'
			ctx.textAlign = 'left'
			ctx.textBaseline = 'alphabetic'
			ctx.fillText(sectorNode.data.name, x0 + 3, y0 + 11, x1 - x0 - 6)
		}

		// Leaf tiles
		for (const leaf of root.leaves()) {
			const { x0, y0, x1, y1 } = leaf as any
			const w = x1 - x0
			const h = y1 - y0
			if (w < 2 || h < 2) continue

			const d: HierarchyLeaf = leaf.data
			const color = scoreToColor(d.score)

			ctx.globalAlpha = 0.88
			ctx.fillStyle = color
			ctx.fillRect(x0, y0, w, h)
			ctx.globalAlpha = 1

			ctx.strokeStyle = 'rgba(0,0,0,0.25)'
			ctx.lineWidth = 0.5
			ctx.strokeRect(x0 + 0.25, y0 + 0.25, w - 0.5, h - 0.5)

			if (w > 20 && h > 14) {
				const fontSize = Math.min(11, Math.max(7, Math.floor(Math.min(w, h) * 0.3)))
				ctx.font = `bold ${fontSize}px Inter, system-ui, sans-serif`
				ctx.fillStyle = 'rgba(0,0,0,0.75)'
				ctx.textAlign = 'center'
				ctx.textBaseline = 'middle'
				ctx.fillText(d.symbol, x0 + w / 2, y0 + h / 2, w - 4)
			}

			leaves.push({ ...d, x0, y0, x1, y1 })
		}

		ctx.textAlign = 'left'
		ctx.textBaseline = 'alphabetic'
		leafNodesRef.current = leaves
	}, [hierarchyData])

	useEffect(() => {
		const container = containerRef.current
		if (!container) return
		const obs = new ResizeObserver((entries) => {
			const { width, height } = entries[0].contentRect
			draw(width, height)
		})
		obs.observe(container)
		return () => obs.disconnect()
	}, [draw])

	const hitTest = useCallback((e: React.MouseEvent<HTMLCanvasElement>): LeafNode | null => {
		const rect = canvasRef.current!.getBoundingClientRect()
		const mx = e.clientX - rect.left
		const my = e.clientY - rect.top
		return leafNodesRef.current.find((l) => mx >= l.x0 && mx <= l.x1 && my >= l.y0 && my <= l.y1) ?? null
	}, [])

	const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
		const found = hitTest(e)
		if (found) {
			setHovering(true)
			setTooltip({ clientX: e.clientX, clientY: e.clientY, leaf: found })
		} else {
			setHovering(false)
			setTooltip(null)
		}
	}, [hitTest])

	const handleMouseLeave = useCallback(() => {
		setHovering(false)
		setTooltip(null)
	}, [])

	const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
		const found = hitTest(e)
		if (found && onSelectSymbol) onSelectSymbol(found.symbol)
	}, [hitTest, onSelectSymbol])

	return (
		<div className={`sheatmap${fullscreen ? ' sheatmap--fullscreen' : ''}`}>
			<div className="sheatmap-header">
				<div className="sheatmap-legend">
					<span className="sheatmap-legend-label sheatmap-legend-low">Low</span>
					<div className="sheatmap-legend-bar" />
					<span className="sheatmap-legend-label sheatmap-legend-high">High</span>
				</div>
				<label className="sheatmap-weight-toggle">
					<input
						type="checkbox"
						checked={equalWeight}
						onChange={(e) => setEqualWeight(e.target.checked)}
					/>
					<span>Equal Weight</span>
				</label>
				<button
					className="sheatmap-expand-btn"
					onClick={() => setFullscreen((f) => !f)}
					title={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
				>
					{fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
				</button>
			</div>
			<div ref={containerRef} className="sheatmap-canvas-wrap">
				<canvas
					ref={canvasRef}
					className="sheatmap-canvas"
					style={{ cursor: hovering ? 'pointer' : 'crosshair' }}
					onMouseMove={handleMouseMove}
					onMouseLeave={handleMouseLeave}
					onClick={handleClick}
				/>
			</div>
			{tooltip && (
				<div
					className="sheatmap-tooltip"
					style={{ left: tooltip.clientX + 14, top: tooltip.clientY - 10 }}
				>
					<div className="sheatmap-tt-symbol">{tooltip.leaf.symbol}</div>
					<div className="sheatmap-tt-name">{tooltip.leaf.name}</div>
					<div className="sheatmap-tt-row">
						<span>Score</span>
						<span style={{ color: scoreToColor(tooltip.leaf.score) }}>
							{tooltip.leaf.score.toFixed(1)}%
						</span>
					</div>
					<div className="sheatmap-tt-row">
						<span>Sector</span>
						<span>{tooltip.leaf.sector ?? '—'}</span>
					</div>
					<div className="sheatmap-tt-row">
						<span>Industry</span>
						<span>{tooltip.leaf.industry ?? '—'}</span>
					</div>
					<div className="sheatmap-tt-row">
						<span>Mkt Cap</span>
						<span>{formatMarketCap(tooltip.leaf.market_cap)}</span>
					</div>
				</div>
			)}
		</div>
	)
}

export default SmartHeatmap
