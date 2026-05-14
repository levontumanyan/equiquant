/**
 * Scoring functions translated from core/scorers.py
 */

export const sigmoidScore = (val: number, best: number, worst: number): number => {
	const midpoint = (best + worst) / 2;
	if (Math.abs(best - worst) < 1e-9) return val >= best ? 1 : 0;
	try {
		const k = Math.log(1 / 19) / (best - midpoint);
		return 1 / (1 + Math.exp(k * (val - midpoint)));
	} catch {
		try {
			const k_dir = Math.log(1 / 19) / (best - midpoint);
			return (k_dir * (val - midpoint)) < 0 ? 1 : 0;
		} catch {
			return val === best ? 1 : 0;
		}
	}
};

export const linearScore = (val: number, best: number, worst: number): number => {
	if (Math.abs(best - worst) < 1e-9) return val >= best ? 1 : 0;
	let pct: number;
	if (best > worst) {
		pct = (val - worst) / (best - worst);
	} else {
		pct = (worst - val) / (worst - best);
	}
	return Math.max(0, Math.min(1, pct));
};

export const bellScore = (val: number, target: number, width: number): number => {
	if (width === 0) return 0;
	try {
		return Math.exp(-0.5 * Math.pow((val - target) / width, 2));
	} catch {
		return 0;
	}
};

export const plateauScore = (val: number, targetMin: number, targetMax: number, width: number): number => {
	if (val >= targetMin && val <= targetMax) return 1;
	const edge = val < targetMin ? targetMin : targetMax;
	if (width === 0) return 0;
	try {
		return Math.exp(-0.5 * Math.pow((val - edge) / width, 2));
	} catch {
		return 0;
	}
};

export const thresholdScore = (val: number, threshold: number): number => {
	return val >= threshold ? 1 : 0;
};
