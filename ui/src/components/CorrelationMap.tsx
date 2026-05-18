import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import * as d3 from 'd3'
import { Search } from 'lucide-react'
import type { AssetAnalysis, MetricResult } from '../types'
import {
	buildSimilarityNodes,
	computeEdges,
	buildSectorHierarchy,
	isHiddenGem,
	type SimilarityNode,
	type SimilarityEdge,
} from '../utils/similarity'
import './CorrelationMap.css'

type Mode = 'force' | 'pack' | 'radial'

const SECTOR_COLORS: Record<string, string> = {
	'Technology':             '#818cf8',
	'Healthcare':             '#34d399',
	'Financial Services':     '#22d3ee',
	'Financials':             '#22d3ee',
	'Consumer Cyclical':      '#fbbf24',
	'Consumer Defensive':     '#f59e0b',
	'Consumer':               '#fbbf24',
	'Energy':                 '#fb7185',
	'Industrials':            '#c084fc',
	'Basic Materials':        '#f472b6',
	'Materials':              '#f472b6',
	'Real Estate':            '#2dd4bf',
	'Utilities':              '#facc15',
	'Communication Services': '#fb923c',
	'Communication':          '#fb923c',
	'Unknown':                '#6b7280',
}

function sectorColor(sector: string | null): string {
	if (!sector) return SECTOR_COLORS['Unknown']
	return SECTOR_COLORS[sector] ?? SECTOR_COLORS['Unknown']
}

function nodeRadius(score: number): number {
	return 8 + (score / 100) * 16
}

function scoreClass(score: number): string {
	if (score >= 68) return 'high'
	if (score >= 42) return 'mid'
	return 'low'
}

function barColor(score: number): string {
	if (score >= 0.68) return '#4ade80'
	if (score >= 0.42) return '#fbbf24'
	return '#f87171'
}

// ── Glass helpers ──────────────────────────────────────────────────────────────

function sectorId(sector: string | null): string {
	return (sector ?? 'Unknown').replace(/[^a-zA-Z0-9]/g, '_')
}

function setupGlassDefs(
	defs: d3.Selection<SVGDefsElement, unknown, null, undefined>,
	sectors: string[],
) {
	// Shared specular shine — strong upper-left highlight
	const shine = defs.append('radialGradient')
		.attr('id', 'glass-shine')
		.attr('cx', '30%').attr('cy', '22%').attr('r', '60%')
		.attr('fx', '30%').attr('fy', '22%')
	shine.append('stop').attr('offset', '0%').attr('stop-color', '#fff').attr('stop-opacity', 0.72)
	shine.append('stop').attr('offset', '45%').attr('stop-color', '#fff').attr('stop-opacity', 0.12)
	shine.append('stop').attr('offset', '100%').attr('stop-color', '#fff').attr('stop-opacity', 0)

	// Bottom rim reflection
	const reflect = defs.append('radialGradient')
		.attr('id', 'glass-reflect')
		.attr('cx', '50%').attr('cy', '100%').attr('r', '45%')
		.attr('fx', '50%').attr('fy', '100%')
	reflect.append('stop').attr('offset', '0%').attr('stop-color', '#fff').attr('stop-opacity', 0.22)
	reflect.append('stop').attr('offset', '100%').attr('stop-color', '#fff').attr('stop-opacity', 0)

	// Per-sector: colored body gradient + outer glow filter
	sectors.forEach(sector => {
		const sid = sectorId(sector)
		const color = sectorColor(sector)

		// Vibrant body fill: color center → dark transparent edge
		const grad = defs.append('radialGradient')
			.attr('id', `glass-fill-${sid}`)
			.attr('cx', '50%').attr('cy', '50%').attr('r', '50%')
		grad.append('stop').attr('offset', '0%').attr('stop-color', color).attr('stop-opacity', 0.55)
		grad.append('stop').attr('offset', '70%').attr('stop-color', color).attr('stop-opacity', 0.25)
		grad.append('stop').attr('offset', '100%').attr('stop-color', color).attr('stop-opacity', 0.08)

		// Outer glow filter
		const filter = defs.append('filter')
			.attr('id', `glass-glow-${sid}`)
			.attr('x', '-50%').attr('y', '-50%')
			.attr('width', '200%').attr('height', '200%')
		filter.append('feGaussianBlur').attr('in', 'SourceGraphic').attr('stdDeviation', '6').attr('result', 'blur')
		const fm = filter.append('feMerge')
		fm.append('feMergeNode').attr('in', 'blur')
		fm.append('feMergeNode').attr('in', 'SourceGraphic')
	})

	// Single shared gem glow filter — all gem rings reference this one id
	const gemFilter = defs.append('filter')
		.attr('id', 'gem-glow')
		.attr('x', '-60%').attr('y', '-60%')
		.attr('width', '220%').attr('height', '220%')
	gemFilter.append('feGaussianBlur').attr('in', 'SourceGraphic').attr('stdDeviation', '5').attr('result', 'blur')
	const gemMerge = gemFilter.append('feMerge')
	gemMerge.append('feMergeNode').attr('in', 'blur')
	gemMerge.append('feMergeNode').attr('in', 'SourceGraphic')
}

function applyGlass(
	g: d3.Selection<SVGGElement, unknown, null, undefined>,
	r: number,
	color: string,
	sector: string | null,
	gem: boolean,
	symbol: string,
) {
	const sid = sectorId(sector)
	const fontSize = Math.max(8, Math.min(12, r - 2))

	// 1. Outer colored aura glow
	g.append('circle')
		.attr('r', r + 7)
		.attr('fill', color)
		.attr('fill-opacity', 0.14)
		.style('filter', `blur(${Math.round(r * 0.55)}px)`)

	// 2. Gem ring (behind the main body) — references the single shared filter
	if (gem) {
		g.append('circle')
			.attr('r', r + 5)
			.attr('fill', 'none')
			.attr('stroke', '#2ed573')
			.attr('stroke-width', 1.5)
			.attr('stroke-opacity', 0.65)
			.attr('filter', 'url(#gem-glow)')
	}

	// 3. Main glass body — vibrant sector fill
	g.append('circle')
		.attr('class', 'node-circle')
		.attr('r', r)
		.attr('fill', `url(#glass-fill-${sid})`)
		.attr('stroke', color)
		.attr('stroke-width', gem ? 1.8 : 1.2)
		.attr('stroke-opacity', gem ? 1 : 0.65)

	// 4. Specular shine — large upper-left highlight
	g.append('circle')
		.attr('r', r)
		.attr('fill', 'url(#glass-shine)')
		.attr('pointer-events', 'none')

	// 5. Bottom rim reflection
	g.append('circle')
		.attr('r', r)
		.attr('fill', 'url(#glass-reflect)')
		.attr('pointer-events', 'none')

	// 6. Inner border ring for glass depth
	g.append('circle')
		.attr('r', r - 1.5)
		.attr('fill', 'none')
		.attr('stroke', 'rgba(255,255,255,0.15)')
		.attr('stroke-width', 0.75)
		.attr('pointer-events', 'none')

	// 7. Label — clean, light Inter typeface
	g.append('text')
		.attr('class', 'node-label')
		.attr('text-anchor', 'middle')
		.attr('dy', '0.36em')
		.attr('font-family', 'Inter, system-ui, sans-serif')
		.attr('font-size', fontSize)
		.attr('font-weight', 600)
		.attr('letter-spacing', '0.06em')
		.attr('fill', '#fff')
		.attr('fill-opacity', 0.95)
		.text(symbol)
}

// ── Component ──────────────────────────────────────────────────────────────────

interface TooltipState {
	x: number
	y: number
	node: SimilarityNode
	asset: AssetAnalysis
	isGem: boolean
}

interface Props {
	data: AssetAnalysis[]
}

export default function CorrelationMap({ data }: Props) {
	const svgRef = useRef<SVGSVGElement>(null)
	const wrapRef = useRef<HTMLDivElement>(null)
	const [mode, setMode] = useState<Mode>('force')
	const [query, setQuery] = useState('')
	const [tooltip, setTooltip] = useState<TooltipState | null>(null)
	const [renderKey, setRenderKey] = useState(0)
	const [edgeCount, setEdgeCount] = useState(0)
	const simRef = useRef<d3.Simulation<SimilarityNode, SimilarityEdge> | null>(null)

	const assetMap = useMemo(() => {
		const map = new Map<string, AssetAnalysis>()
		data.forEach(a => map.set(a.symbol, a))
		return map
	}, [data])

	useEffect(() => {
		const el = wrapRef.current
		if (!el) return
		const ro = new ResizeObserver(() => setRenderKey(k => k + 1))
		ro.observe(el)
		return () => ro.disconnect()
	}, [])

	function getSize(): { w: number; h: number } {
		const el = svgRef.current
		if (!el) return { w: 800, h: 560 }
		const rect = el.getBoundingClientRect()
		return { w: rect.width || 800, h: rect.height || 560 }
	}

	const handleNodeHover = useCallback((
		event: MouseEvent,
		node: SimilarityNode | null,
	) => {
		if (!node) { setTooltip(null); return }
		const asset = assetMap.get(node.id)
		if (!asset) return
		const rect = wrapRef.current?.getBoundingClientRect()
		if (!rect) return
		setTooltip({
			x: event.clientX - rect.left + 14,
			y: event.clientY - rect.top - 10,
			node,
			asset,
			isGem: isHiddenGem(node, asset),
		})
	}, [assetMap])

	// ── FORCE CLUSTER ──────────────────────────────────────────────────────────
	const renderForce = useCallback((
		svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
		nodes: SimilarityNode[],
		edges: SimilarityEdge[],
		w: number,
		h: number,
	) => {
		svg.selectAll('*').remove()

		const nodeMap = new Map(nodes.map(n => [n.id, n]))
		const sectors = [...new Set(nodes.map(n => n.sector ?? 'Unknown'))]
		const defs = svg.append('defs')
		setupGlassDefs(defs, sectors)

		const zg = svg.append('g')
		svg.call(
			d3.zoom<SVGSVGElement, unknown>()
				.scaleExtent([0.25, 5])
				.on('zoom', e => zg.attr('transform', e.transform)),
		)

		const linkSel = zg.append('g')
			.selectAll<SVGLineElement, SimilarityEdge>('line')
			.data(edges)
			.join('line')
			.attr('stroke', d => {
				const srcId = typeof d.source === 'object' ? (d.source as any).id : d.source
				const src = nodeMap.get(srcId)
				return sectorColor(src?.sector ?? null)
			})
			.attr('stroke-width', d => d.strength * 1.5)
			.attr('stroke-opacity', d => (d.strength - 0.72) * 2.5)

		const nodeGs = zg.append('g')
			.selectAll<SVGGElement, SimilarityNode>('g')
			.data(nodes, d => d.id)
			.join('g')
			.attr('class', 'node-g')
			.style('cursor', 'pointer')

		nodeGs.each(function(d) {
			const g = d3.select<SVGGElement, SimilarityNode>(this)
			const color = sectorColor(d.sector)
			const gem = isHiddenGem(d, assetMap.get(d.id))
			const r = nodeRadius(d.score)
			applyGlass(g as any, r, color, d.sector, gem, d.id)
		})

		nodeGs
			.on('mousemove', (event, d) => handleNodeHover(event, d))
			.on('mouseleave', () => setTooltip(null))

		let sim: d3.Simulation<SimilarityNode, SimilarityEdge>

		const drag = d3.drag<SVGGElement, SimilarityNode>()
			.on('start', (event, d) => {
				if (!event.active) sim.alphaTarget(0.3).restart()
				d.fx = d.x; d.fy = d.y
			})
			.on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
			.on('end', (event, d) => {
				if (!event.active) sim.alphaTarget(0)
				d.fx = null; d.fy = null
			})
		nodeGs.call(drag)

		sim = d3.forceSimulation<SimilarityNode>(nodes)
			.force('link', d3.forceLink<SimilarityNode, SimilarityEdge>(edges)
				.id(d => d.id)
				.strength(d => d.strength * 0.35)
				.distance(80)
			)
			.force('charge', d3.forceManyBody<SimilarityNode>().strength(-200))
			.force('center', d3.forceCenter(w / 2, h / 2))
			.force('collision', d3.forceCollide<SimilarityNode>().radius(d => nodeRadius(d.score) + 6))

		simRef.current = sim

		sim.on('tick', () => {
			linkSel
				.attr('x1', d => ((d.source as unknown) as SimilarityNode).x ?? 0)
				.attr('y1', d => ((d.source as unknown) as SimilarityNode).y ?? 0)
				.attr('x2', d => ((d.target as unknown) as SimilarityNode).x ?? 0)
				.attr('y2', d => ((d.target as unknown) as SimilarityNode).y ?? 0)
			nodeGs.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
		})
	}, [handleNodeHover, assetMap])

	// ── SECTOR PACK ────────────────────────────────────────────────────────────
	const renderPack = useCallback((
		svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
		nodes: SimilarityNode[],
		w: number,
		h: number,
	) => {
		svg.selectAll('*').remove()

		const nodeMap = new Map(nodes.map(n => [n.id, n]))
		const sectors = [...new Set(nodes.map(n => n.sector ?? 'Unknown'))]
		const defs = svg.append('defs')
		setupGlassDefs(defs, sectors)

		const hierarchy = buildSectorHierarchy(nodes)
		const root = d3.hierarchy<object>(hierarchy as object)
			.sum((d: any) => d.node ? d.node.score : 0)
			.sort((a, b) => (b.value ?? 0) - (a.value ?? 0))

		d3.pack<object>().size([w - 20, h - 20]).padding(14)(root)

		const zg = svg.append('g').attr('transform', 'translate(10,10)')
		svg.call(
			d3.zoom<SVGSVGElement, unknown>()
				.scaleExtent([0.3, 6])
				.on('zoom', e => zg.attr('transform', e.transform)),
		)

		const all = root.descendants()

		// Sector bubbles
		zg.selectAll<SVGGElement, d3.HierarchyCircularNode<object>>('.sb-g')
			.data(all.filter(d => d.depth === 1))
			.join('g')
			.each(function(d) {
				const g = d3.select(this)
				const color = sectorColor((d.data as any).name)
				const r = (d as any).r
				const cx = (d as any).x
				const cy = (d as any).y
				// Sector glass ring
				g.append('circle')
					.attr('cx', cx).attr('cy', cy).attr('r', r)
					.attr('fill', color).attr('fill-opacity', 0.04)
					.attr('stroke', color).attr('stroke-width', 1).attr('stroke-opacity', 0.2)
					.attr('stroke-dasharray', '4 3')
				g.append('text')
					.attr('x', cx).attr('y', cy - r - 7)
					.attr('text-anchor', 'middle')
					.attr('font-size', 9).attr('font-weight', 700)
					.attr('fill', color).attr('fill-opacity', 0.65)
					.attr('letter-spacing', '0.08em')
					.attr('font-family', 'Inter, system-ui, sans-serif')
					.text((d.data as any).name.toUpperCase())
			})

		// Asset leaves
		const leaves = all.filter(d => d.depth === 3) as d3.HierarchyCircularNode<object>[]
		const leafGs = zg.selectAll<SVGGElement, d3.HierarchyCircularNode<object>>('.lf')
			.data(leaves, d => (d.data as any).name)
			.join('g')
			.attr('class', 'lf')
			.attr('transform', d => `translate(${(d as any).x},${(d as any).y})`)
			.style('cursor', 'pointer')

		leafGs.each(function(d) {
			const g = d3.select<SVGGElement, d3.HierarchyCircularNode<object>>(this)
			const symbol = (d.data as any).name
			const node = nodeMap.get(symbol)
			if (!node) return
			const sectorName = (d.parent?.parent?.data as any)?.name ?? null
			const color = sectorColor(sectorName)
			const r = (d as any).r
			const gem = isHiddenGem(node, assetMap.get(symbol))
			applyGlass(g as any, r, color, sectorName, gem, symbol)
		})

		leafGs
			.on('mousemove', (event, d) => {
				const n = nodeMap.get((d.data as any).name)
				if (n) handleNodeHover(event, n)
			})
			.on('mouseleave', () => setTooltip(null))
	}, [handleNodeHover, assetMap])

	// ── RADIAL ORBIT ───────────────────────────────────────────────────────────
	const renderRadial = useCallback((
		svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
		nodes: SimilarityNode[],
		w: number,
		h: number,
	) => {
		svg.selectAll('*').remove()

		const sectors = [...new Set(nodes.map(n => n.sector ?? 'Unknown'))]
		const defs = svg.append('defs')
		setupGlassDefs(defs, sectors)

		const cx = w / 2, cy = h / 2
		const sectorMap = new Map<string, SimilarityNode[]>()
		for (const n of nodes) {
			const s = n.sector ?? 'Unknown'
			if (!sectorMap.has(s)) sectorMap.set(s, [])
			sectorMap.get(s)!.push(n)
		}

		const sectorList = [...sectorMap.keys()]
		const R_HUB = Math.min(w, h) * 0.28
		const R_ORBIT = Math.min(w, h) * 0.12

		const zg = svg.append('g')
		svg.call(
			d3.zoom<SVGSVGElement, unknown>()
				.scaleExtent([0.3, 4])
				.on('zoom', e => zg.attr('transform', e.transform)),
		)

		sectorList.forEach((sector, si) => {
			const ang = (si / sectorList.length) * Math.PI * 2 - Math.PI / 2
			const hx = cx + Math.cos(ang) * R_HUB
			const hy = cy + Math.sin(ang) * R_HUB
			const color = sectorColor(sector)
			const sNodes = sectorMap.get(sector)!.sort((a, b) => b.score - a.score)
			const sid = sectorId(sector)

			// Spoke
			zg.append('line')
				.attr('x1', cx).attr('y1', cy).attr('x2', hx).attr('y2', hy)
				.attr('stroke', color).attr('stroke-opacity', 0.08)
				.attr('stroke-width', 1).attr('stroke-dasharray', '3 5')

			// Orbit ring
			zg.append('circle')
				.attr('cx', hx).attr('cy', hy).attr('r', R_ORBIT)
				.attr('fill', 'none').attr('stroke', color)
				.attr('stroke-opacity', 0.07).attr('stroke-width', 1)

			// Hub glass pill
			const hubG = zg.append('g').attr('transform', `translate(${hx},${hy})`)
			hubG.append('circle')
				.attr('r', 20)
				.attr('fill', `url(#glass-fill-${sid})`)
				.attr('stroke', color).attr('stroke-opacity', 0.4).attr('stroke-width', 1)
			hubG.append('circle').attr('r', 19.5)
				.attr('fill', 'rgba(8,10,18,0.4)').attr('pointer-events', 'none')
			hubG.append('circle').attr('r', 19.5)
				.attr('fill', 'url(#glass-shine)').attr('pointer-events', 'none')
			hubG.append('text')
				.attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
				.attr('font-size', 7.5).attr('font-weight', 800)
				.attr('fill', color).attr('fill-opacity', 0.9)
				.attr('letter-spacing', '0.05em')
				.text(sector.split(' ').map((w: string) => w[0]).join('').toUpperCase())

			// Asset nodes
			sNodes.forEach((node, ni) => {
				const na = (ni / sNodes.length) * Math.PI * 2 - Math.PI / 2
				const nx = hx + Math.cos(na) * R_ORBIT
				const ny = hy + Math.sin(na) * R_ORBIT
				const r = nodeRadius(node.score)
				const gem = isHiddenGem(node, assetMap.get(node.id))

				const g = zg.append('g')
					.attr('transform', `translate(${nx},${ny})`)
					.style('cursor', 'pointer')

				applyGlass(g as any, r, color, sector, gem, node.id)

				g.on('mousemove', (event) => handleNodeHover(event, node))
					.on('mouseleave', () => setTooltip(null))
			})
		})

		// Center point
		zg.append('circle').attr('cx', cx).attr('cy', cy).attr('r', 3)
			.attr('fill', 'rgba(255,255,255,0.15)')
	}, [handleNodeHover, assetMap])

	// ── Main effect ────────────────────────────────────────────────────────────
	useEffect(() => {
		const svg = d3.select(svgRef.current!)
		if (simRef.current) { simRef.current.stop(); simRef.current = null }
		setTooltip(null)
		if (data.length === 0) { svg.selectAll('*').remove(); return }

		const { w, h } = getSize()
		if (w < 10 || h < 10) return

		const nodes = buildSimilarityNodes(data)
		const edges = computeEdges(nodes)
		setEdgeCount(edges.length)

		if (mode === 'force') renderForce(svg, nodes, edges, w, h)
		else if (mode === 'pack') renderPack(svg, nodes, w, h)
		else renderRadial(svg, nodes, w, h)

		return () => { if (simRef.current) { simRef.current.stop(); simRef.current = null } }
	// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [data, mode, renderKey, renderForce, renderPack, renderRadial])

	// ── Search dimming ─────────────────────────────────────────────────────────
	useEffect(() => {
		const svg = d3.select(svgRef.current!)
		const q = query.trim().toUpperCase()
		if (!q) {
			svg.selectAll('.node-g').style('opacity', null)
			svg.selectAll('.lf').style('opacity', null)
			return
		}
		svg.selectAll<SVGGElement, SimilarityNode>('.node-g')
			.style('opacity', d => d.id.includes(q) || d.name.toUpperCase().includes(q) ? 1 : 0.07)
		svg.selectAll<SVGGElement, d3.HierarchyCircularNode<object>>('.lf')
			.style('opacity', d => (d.data as any).name?.toUpperCase().includes(q) ? 1 : 0.07)
	}, [query])

	const uniqueSectors = [...new Set(data.map(a => a.sector ?? 'Unknown'))].slice(0, 10)
	const gemCount = data.filter(a => {
		const n = buildSimilarityNodes([a])
		return isHiddenGem(n[0], a)
	}).length

	const topMetrics = (asset: AssetAnalysis): MetricResult[] =>
		[...asset.results]
			.filter(r => r.raw_value !== null)
			.sort((a, b) => Math.abs(b.score - 0.5) - Math.abs(a.score - 0.5))
			.slice(0, 4)

	const wrapW = wrapRef.current?.clientWidth ?? 800

	return (
		<div className="cmap-root">
			<div className="cmap-toolbar">
				<div className="cmap-mode-group">
					{(['force', 'pack', 'radial'] as Mode[]).map(m => (
						<button
							key={m}
							className={`cmap-mode-btn${mode === m ? ' active' : ''}`}
							onClick={() => setMode(m)}
						>
							{m === 'force' ? 'Force Cluster' : m === 'pack' ? 'Sector Pack' : 'Radial Orbit'}
						</button>
					))}
				</div>
				<div className="cmap-search-wrap">
					<Search size={12} className="cmap-search-icon" />
					<input
						className="cmap-search"
						placeholder="Highlight ticker…"
						value={query}
						onChange={e => setQuery(e.target.value)}
					/>
				</div>
				<div className="cmap-meta">
					<span className="cmap-meta-badge">{data.length} assets</span>
					{mode === 'force' && <span className="cmap-meta-badge">{edgeCount} links</span>}
					{gemCount > 0 && (
						<span className="cmap-meta-badge" style={{ color: '#2ed573', borderColor: 'rgba(46,213,115,0.3)' }}>
							{gemCount} gems
						</span>
					)}
				</div>
			</div>

			<div className="cmap-canvas-wrap" ref={wrapRef}>
				<svg ref={svgRef} className="cmap-svg" />

				{tooltip && (
					<div
						className="cmap-tooltip"
						style={{
							left: Math.min(tooltip.x, wrapW - 290),
							top: Math.max(tooltip.y, 8),
						}}
					>
						<div className="cmap-tip-symbol">{tooltip.node.id}</div>
						<div className="cmap-tip-name">{tooltip.node.name}</div>
						{tooltip.node.sector && (
							<span
								className="cmap-tip-sector"
								style={{
									background: sectorColor(tooltip.node.sector) + '18',
									color: sectorColor(tooltip.node.sector),
									border: `1px solid ${sectorColor(tooltip.node.sector)}35`,
								}}
							>
								{tooltip.node.sector}
							</span>
						)}
						<div className="cmap-tip-score">
							<span className="cmap-tip-score-label">Score</span>
							<span className={`cmap-tip-score-val ${scoreClass(tooltip.node.score)}`}>
								{tooltip.node.score.toFixed(1)}
							</span>
						</div>
						<hr className="cmap-tip-divider" />
						<div className="cmap-tip-metrics">
							{topMetrics(tooltip.asset).map(m => (
								<div key={m.metric} className="cmap-tip-metric-row">
									<span className="cmap-tip-metric-name" title={m.name}>{m.name}</span>
									<div className="cmap-tip-metric-bar-wrap">
										<div
											className="cmap-tip-metric-bar"
											style={{ width: `${m.score * 100}%`, background: barColor(m.score) }}
										/>
									</div>
								</div>
							))}
						</div>
						{tooltip.isGem && <div className="cmap-tip-gem-badge">★ Hidden Gem</div>}
					</div>
				)}

				{data.length === 0 && (
					<div style={{
						position: 'absolute', inset: 0,
						display: 'flex', alignItems: 'center', justifyContent: 'center',
						color: '#374151', fontSize: '0.85rem', fontStyle: 'italic',
					}}>
						Run an analysis to explore the cluster map
					</div>
				)}
			</div>

			{data.length > 0 && (
				<div className="cmap-legend">
					{uniqueSectors.map(s => (
						<div key={s} className="cmap-legend-item">
							<div className="cmap-legend-dot" style={{ background: sectorColor(s) }} />
							<span>{s}</span>
						</div>
					))}
					<div className="cmap-legend-item">
						<div className="cmap-legend-gem" />
						<span>Hidden Gem</span>
					</div>
					<span className="cmap-hint" style={{ marginLeft: 'auto' }}>
						{mode === 'force' ? 'Scroll to zoom · Drag nodes' :
							mode === 'pack' ? 'Scroll to zoom · Nested by sector' :
								'Scroll to zoom · Orbiting by sector'}
					</span>
				</div>
			)}
		</div>
	)
}
