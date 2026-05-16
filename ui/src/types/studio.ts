import type { ScorerType } from './index'

export interface StudioMetric {
	metric: string
	name: string
	asset_type: string
	unit?: string
	is_decimal?: boolean
	type: ScorerType
	best?: number
	worst?: number
	target?: number
	target_min?: number
	target_max?: number
	width?: number
	threshold?: number
	weight: number
	range_min: number
	range_max: number
	formula: string
}
