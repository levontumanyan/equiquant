import React, { useState, useMemo, useEffect } from 'react';
import {
	LineChart,
	Line,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	ResponsiveContainer,
	ReferenceLine
} from 'recharts';
import {
	sigmoidScore,
	linearScore,
	bellScore,
	plateauScore,
	thresholdScore,
	penaltyThresholdScore,
	flatPenaltyScore
} from '../utils/scorers';
import type { Benchmark, ScorerType } from '../types';
import './ScoringExplorer.css';

interface Props {
	initialData?: Benchmark;
}

const ScoringExplorer: React.FC<Props> = ({ initialData }) => {
	const [type, setType] = useState<ScorerType>('sigmoid');
	const [best, setBest] = useState(20);
	const [worst, setWorst] = useState(0);
	const [target, setTarget] = useState(15);
	const [targetMin, setTargetMin] = useState(10);
	const [targetMax, setTargetMax] = useState(20);
	const [width, setWidth] = useState(5);
	const [threshold, setThreshold] = useState(10);
	const [currentVal, setCurrentVal] = useState(10);

	// Sync with initialData when it changes
	useEffect(() => {
		if (initialData) {
			setType(initialData.type);
			if (initialData.best !== undefined) setBest(initialData.best);
			if (initialData.worst !== undefined) setWorst(initialData.worst);
			if (initialData.target !== undefined) setTarget(initialData.target);
			if (initialData.target_min !== undefined) setTargetMin(initialData.target_min);
			if (initialData.target_max !== undefined) setTargetMax(initialData.target_max);
			if (initialData.width !== undefined) setWidth(initialData.width);
			if (initialData.threshold !== undefined) setThreshold(initialData.threshold);
			
			// Set test value to something sensible
			if (initialData.best !== undefined) setCurrentVal(initialData.best);
			else if (initialData.target !== undefined) setCurrentVal(initialData.target);
			else if (initialData.target_min !== undefined) setCurrentVal(initialData.target_min);
		}
	}, [initialData]);

	const data = useMemo(() => {
		const points = [];
		const min = Math.min(best, worst, target - width * 2, targetMin - width * 2, threshold - 5, 0);
		const max = Math.max(best, worst, target + width * 2, targetMax + width * 2, threshold + 5, 30);
		const step = Math.max((max - min) / 100, 0.01);

		for (let i = min; i <= max; i += step) {
			let score = 0;
			if (type === 'sigmoid') score = sigmoidScore(i, best, worst);
			else if (type === 'linear') score = linearScore(i, best, worst);
			else if (type === 'bell_curve') score = bellScore(i, target, width);
			else if (type === 'plateau') score = plateauScore(i, targetMin, targetMax, width);
			else if (type === 'threshold') score = thresholdScore(i, threshold);
			else if (type === 'penalty_threshold') score = penaltyThresholdScore(i, threshold, worst);
			else if (type === 'flat_penalty') score = flatPenaltyScore(i, threshold);

			points.push({
				x: parseFloat(i.toFixed(2)),
				score: parseFloat((score * 100).toFixed(1))
			});
		}
		return points;
	}, [type, best, worst, target, targetMin, targetMax, width, threshold]);

	const currentScore = useMemo(() => {
		if (type === 'sigmoid') return sigmoidScore(currentVal, best, worst);
		if (type === 'linear') return linearScore(currentVal, best, worst);
		if (type === 'bell_curve') return bellScore(currentVal, target, width);
		if (type === 'plateau') return plateauScore(currentVal, targetMin, targetMax, width);
		if (type === 'threshold') return thresholdScore(currentVal, threshold);
		if (type === 'penalty_threshold') return penaltyThresholdScore(currentVal, threshold, worst);
		if (type === 'flat_penalty') return flatPenaltyScore(currentVal, threshold);
		return 0;
	}, [currentVal, type, best, worst, target, targetMin, targetMax, width, threshold]);

	return (
		<div className="explorer-container">
			<section className="explorer-controls">
				{initialData && (
					<div className="metric-info">
						<h3>{initialData.name}</h3>
						<code>{initialData.metric}</code>
					</div>
				)}
				
				<div className="control-group">
					<label>Function Type</label>
					<select value={type} onChange={(e) => setType(e.target.value as ScorerType)}>
						<option value="sigmoid">Sigmoid (Smooth)</option>
						<option value="linear">Linear</option>
						<option value="bell_curve">Bell Curve (Target)</option>
						<option value="plateau">Plateau (Range)</option>
						<option value="threshold">Threshold (Pass/Fail)</option>
						<option value="penalty_threshold">Penalty Range</option>
						<option value="flat_penalty">Flat Penalty</option>
					</select>
				</div>

				{(type === 'sigmoid' || type === 'linear' || type === 'penalty_threshold') && (
					<>
						{type === 'penalty_threshold' ? (
							<div className="control-group">
								<label>Threshold (0%): {threshold}</label>
								<input type="range" min="-50" max="100" step="0.1" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
							</div>
						) : (
							<div className="control-group">
								<label>Best Value (100%): {best}</label>
								<input type="range" min="-50" max="100" step="0.1" value={best} onChange={(e) => setBest(Number(e.target.value))} />
							</div>
						)}
						<div className="control-group">
							<label>{type === 'penalty_threshold' ? 'Worst Value (-100%)' : 'Worst Value (0%)'}: {worst}</label>
							<input type="range" min="-50" max="100" step="0.1" value={worst} onChange={(e) => setWorst(Number(e.target.value))} />
						</div>
					</>
				)}

				{type === 'bell_curve' && (
					<>
						<div className="control-group">
							<label>Target Value: {target}</label>
							<input type="range" min="-50" max="100" step="0.1" value={target} onChange={(e) => setTarget(Number(e.target.value))} />
						</div>
						<div className="control-group">
							<label>Width (Sigma): {width}</label>
							<input type="range" min="0.1" max="20" step="0.1" value={width} onChange={(e) => setWidth(Number(e.target.value))} />
						</div>
					</>
				)}

				{type === 'plateau' && (
					<>
						<div className="control-group">
							<label>Target Min: {targetMin}</label>
							<input type="range" min="-50" max="100" step="0.1" value={targetMin} onChange={(e) => setTargetMin(Number(e.target.value))} />
						</div>
						<div className="control-group">
							<label>Target Max: {targetMax}</label>
							<input type="range" min="-50" max="100" step="0.1" value={targetMax} onChange={(e) => setTargetMax(Number(e.target.value))} />
						</div>
						<div className="control-group">
							<label>Decay Width: {width}</label>
							<input type="range" min="0.1" max="20" step="0.1" value={width} onChange={(e) => setWidth(Number(e.target.value))} />
						</div>
					</>
				)}

				{type === 'threshold' && (
					<div className="control-group">
						<label>Threshold: {threshold}</label>
						<input type="range" min="-50" max="100" step="0.1" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
					</div>
				)}

				{type === 'flat_penalty' && (
					<div className="control-group">
						<label>Threshold: {threshold}</label>
						<input type="range" min="-50" max="100" step="0.1" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
					</div>
				)}

				<div className="control-group tester">
					<label>Test Value: {currentVal}</label>
					<input type="range" min="-50" max="100" step="0.1" value={currentVal} onChange={(e) => setCurrentVal(Number(e.target.value))} />
					<div className="result-badge">
						Score: {(currentScore * 100).toFixed(1)}%
					</div>
				</div>
			</section>

			<section className="explorer-chart">
				<ResponsiveContainer width="100%" height={400}>
					<LineChart data={data}>
						<CartesianGrid strokeDasharray="3 3" stroke="#333" />
						<XAxis dataKey="x" stroke="#888" />
						<YAxis domain={['auto', 'auto']} stroke="#888" />
						<Tooltip 
							contentStyle={{ backgroundColor: '#222', border: '1px solid #444', color: '#fff' }}
							itemStyle={{ color: '#646cff' }}
						/>
						<Line type="monotone" dataKey="score" stroke="#646cff" strokeWidth={3} dot={false} isAnimationActive={false} />
						<ReferenceLine x={currentVal} stroke="#ff4757" strokeDasharray="5 5" label={{ position: 'top', value: 'Test', fill: '#ff4757' }} />
					</LineChart>
				</ResponsiveContainer>
			</section>
		</div>
	);
};

export default ScoringExplorer;
