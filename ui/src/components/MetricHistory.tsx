import React, { useState, useEffect } from 'react';
import {
	LineChart,
	Line,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	ResponsiveContainer,
	AreaChart,
	Area
} from 'recharts';
import './MetricHistory.css';

interface Props {
	metricKey: string;
	metricName: string;
}

interface HistoryPoint {
	timestamp: string;
	value: number;
	symbol?: string;
}

const MetricHistory: React.FC<Props> = ({ metricKey, metricName }) => {
	const [data, setData] = useState<HistoryPoint[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchHistory = async () => {
			setLoading(true);
			try {
				const res = await fetch(`http://localhost:8000/api/metrics/${metricKey}/history?limit=50`);
				if (res.ok) {
					const history = await res.json();
					// Recharts likes chronological order
					setData(history.reverse());
				}
			} catch (error) {
				console.error('Error fetching metric history:', error);
			} finally {
				setLoading(false);
			}
		};
		fetchHistory();
	}, [metricKey]);

	if (loading) return <div className="loading-small">Loading history...</div>;
	if (data.length === 0) return <div className="no-data">No historical data found for this metric.</div>;

	return (
		<div className="metric-history-container">
			<h3>Historical Values: {metricName}</h3>
			<div className="chart-wrapper">
				<ResponsiveContainer width="100%" height={250}>
					<AreaChart data={data}>
						<defs>
							<linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
								<stop offset="5%" stopColor="#646cff" stopOpacity={0.3}/>
								<stop offset="95%" stopColor="#646cff" stopOpacity={0}/>
							</linearGradient>
						</defs>
						<CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
						<XAxis 
							dataKey="timestamp" 
							hide 
						/>
						<YAxis 
							stroke="#888" 
							fontSize={12}
							tickFormatter={(val) => val.toFixed(2)}
						/>
						<Tooltip 
							contentStyle={{ background: '#1a1a1a', border: '1px solid #333', color: '#ccc' }}
							itemStyle={{ color: '#646cff' }}
							labelFormatter={(label) => new Date(label).toLocaleString()}
						/>
						<Area 
							type="monotone" 
							dataKey="value" 
							stroke="#646cff" 
							fillOpacity={1} 
							fill="url(#colorValue)" 
						/>
					</AreaChart>
				</ResponsiveContainer>
			</div>
			<p className="chart-note">Showing last {data.length} data points from the system logs.</p>
		</div>
	);
};

export default MetricHistory;
