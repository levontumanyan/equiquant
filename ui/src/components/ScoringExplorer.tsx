import React, { useState, useMemo } from 'react';
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
import { sigmoidScore, linearScore, bellScore, thresholdScore } from '../utils/scorers';
import './ScoringExplorer.css';

type ScorerType = 'sigmoid' | 'linear' | 'bell_curve' | 'threshold';

const ScoringExplorer: React.FC = () => {
	const [type, setType] = useState<ScorerType>('sigmoid');
	const [best, setBest] = useState(20);
	const [worst, setWorst] = useState(0);
	const [target, setTarget] = useState(15);
	const [width, setWidth] = useState(5);
	const [threshold, setThreshold] = useState(10);
	const [currentVal, setCurrentVal] = useState(10);

	const data = useMemo(() => {
		const points = [];
		const min = Math.min(best, worst, target - width * 2, threshold - 5, 0);
		const max = Math.max(best, worst, target + width * 2, threshold + 5, 30);
		const step = (max - min) / 100;

		for (let i = min; i <= max; i += step) {
			let score = 0;
			if (type === 'sigmoid') score = sigmoidScore(i, best, worst);
			else if (type === 'linear') score = linearScore(i, best, worst);
			else if (type === 'bell_curve') score = bellScore(i, target, width);
			else if (type === 'threshold') score = thresholdScore(i, threshold);

			points.push({
				x: parseFloat(i.toFixed(2)),
				score: parseFloat((score * 100).toFixed(1))
			});
		}
		return points;
	}, [type, best, worst, target, width, threshold]);

	const currentScore = useMemo(() => {
		if (type === 'sigmoid') return sigmoidScore(currentVal, best, worst);
		if (type === 'linear') return linearScore(currentVal, best, worst);
		if (type === 'bell_curve') return bellScore(currentVal, target, width);
		if (type === 'threshold') return thresholdScore(currentVal, threshold);
		return 0;
	}, [currentVal, type, best, worst, target, width, threshold]);

	return (
		<div className="explorer-container">
			<section className="explorer-controls">
				<div className="control-group">
					<label>Function Type</label>
					<select value={type} onChange={(e) => setType(e.target.value as ScorerType)}>
						<option value="sigmoid">Sigmoid (Smooth)</option>
						<option value="linear">Linear</option>
						<option value="bell_curve">Bell Curve (Target)</option>
						<option value="threshold">Threshold (Pass/Fail)</option>
					</select>
				</div>

				{type === 'sigmoid' || type === 'linear' ? (
					<>
						<div className="control-group">
							<label>Best Value (100%): {best}</label>
							<input type="range" min="-50" max="100" value={best} onChange={(e) => setBest(Number(e.target.value))} />
						</div>
						<div className="control-group">
							<label>Worst Value (0%): {worst}</label>
							<input type="range" min="-50" max="100" value={worst} onChange={(e) => setWorst(Number(e.target.value))} />
						</div>
					</>
				) : null}

				{type === 'bell_curve' && (
					<>
						<div className="control-group">
							<label>Target Value: {target}</label>
							<input type="range" min="-50" max="100" value={target} onChange={(e) => setTarget(Number(e.target.value))} />
						</div>
						<div className="control-group">
							<label>Width (Sigma): {width}</label>
							<input type="range" min="0.1" max="20" step="0.1" value={width} onChange={(e) => setWidth(Number(e.target.value))} />
						</div>
					</>
				)}

				{type === 'threshold' && (
					<div className="control-group">
						<label>Threshold: {threshold}</label>
						<input type="range" min="-50" max="100" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
					</div>
				)}

				<div className="control-group tester">
					<label>Test Value: {currentVal}</label>
					<input type="range" min="-50" max="100" value={currentVal} onChange={(e) => setCurrentVal(Number(e.target.value))} />
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
						<YAxis domain={[0, 100]} stroke="#888" />
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
