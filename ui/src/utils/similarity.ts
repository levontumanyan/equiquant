import type { AssetAnalysis } from '../types'

export interface SimilarityNode {
	id: string
	name: string
	sector: string | null
	industry: string | null
	score: number
	metrics: Record<string, number>
	x?: number
	y?: number
	fx?: number | null
	fy?: number | null
}

export interface SimilarityEdge {
	source: string
	target: string
	strength: number
}

export function buildSimilarityNodes(assets: AssetAnalysis[]): SimilarityNode[] {
	return assets.map(asset => {
		const metrics: Record<string, number> = {}
		for (const r of asset.results) {
			if (r.raw_value !== null) {
				metrics[r.metric] = r.score
			}
		}
		return {
			id: asset.symbol,
			name: asset.name,
			sector: asset.sector,
			industry: asset.industry,
			score: asset.score,
			metrics,
		}
	})
}

function euclideanDistance(a: Record<string, number>, b: Record<string, number>): number {
	const sharedKeys = Object.keys(a).filter(k => k in b)
	if (sharedKeys.length === 0) return 1
	let sum = 0
	for (const k of sharedKeys) {
		const diff = a[k] - b[k]
		sum += diff * diff
	}
	return Math.sqrt(sum / sharedKeys.length)
}

export function computeEdges(nodes: SimilarityNode[], threshold = 0.72): SimilarityEdge[] {
	const edges: SimilarityEdge[] = []
	for (let i = 0; i < nodes.length; i++) {
		for (let j = i + 1; j < nodes.length; j++) {
			const dist = euclideanDistance(nodes[i].metrics, nodes[j].metrics)
			const similarity = 1 / (1 + dist)
			if (similarity >= threshold) {
				edges.push({ source: nodes[i].id, target: nodes[j].id, strength: similarity })
			}
		}
	}
	return edges
}

export function isHiddenGem(node: SimilarityNode, assets: AssetAnalysis[]): boolean {
	const asset = assets.find(a => a.symbol === node.id)
	if (!asset) return false
	if (asset.score < 62) return false
	const peMetric = asset.results.find(r => r.metric === 'pe_ratio' || r.metric === 'forward_pe')
	const qualityMetric = asset.results.find(r => r.metric === 'return_on_equity' || r.metric === 'profit_margin')
	const hasValueSignal = peMetric && peMetric.score > 0.52
	const hasQualitySignal = qualityMetric && qualityMetric.score > 0.55
	return !!(hasValueSignal && hasQualitySignal)
}

export function buildSectorHierarchy(nodes: SimilarityNode[]): SectorHierarchyRoot {
	const sectorMap = new Map<string, Map<string, SimilarityNode[]>>()
	for (const node of nodes) {
		const sector = node.sector ?? 'Unknown'
		const industry = node.industry ?? 'Other'
		if (!sectorMap.has(sector)) sectorMap.set(sector, new Map())
		const industryMap = sectorMap.get(sector)!
		if (!industryMap.has(industry)) industryMap.set(industry, [])
		industryMap.get(industry)!.push(node)
	}
	const children: SectorGroup[] = []
	for (const [sector, industries] of sectorMap) {
		const industryGroups: IndustryGroup[] = []
		for (const [industry, assetNodes] of industries) {
			industryGroups.push({
				name: industry,
				children: assetNodes.map(n => ({ name: n.id, node: n })),
			})
		}
		children.push({ name: sector, children: industryGroups })
	}
	return { name: 'root', children }
}

export interface AssetLeaf { name: string; node: SimilarityNode }
export interface IndustryGroup { name: string; children: AssetLeaf[] }
export interface SectorGroup { name: string; children: IndustryGroup[] }
export interface SectorHierarchyRoot { name: string; children: SectorGroup[] }
