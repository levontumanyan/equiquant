export type ScorerType =
	| 'sigmoid'
	| 'linear'
	| 'bell_curve'
	| 'plateau'
	| 'threshold'
	| 'penalty_threshold'
	| 'flat_penalty'

export interface Benchmark {
	metric: string;
	name: string;
	type: ScorerType;
	weight: number;
	asset_type: string;
	is_penalty?: boolean;
	unit?: string;
	is_decimal?: boolean;
	display_key?: string;
	best?: number;
	worst?: number;
	target?: number;
	target_min?: number;
	target_max?: number;
	width?: number;
	threshold?: number;
}

export interface MetricResult {
	metric: string;
	name: string;
	value: any;
	raw_value: number | null;
	score: number;
	weight: number;
	status: string;
	is_penalty?: boolean;
	source?: string;
}

export interface AssetAnalysis {
	symbol: string;
	name: string;
	sector: string | null;
	industry: string | null;
	score: number;
	results: MetricResult[];
	raw_metrics?: Record<string, unknown> | null;
	sources?: Record<string, string> | null;
	market_cap?: number | null;
}
