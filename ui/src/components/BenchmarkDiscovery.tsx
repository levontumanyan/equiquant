import React, { useState, useEffect } from 'react';
import { Search, Filter, Play, BarChart2 } from 'lucide-react';
import type { Benchmark } from '../types';
import MetricHistory from './MetricHistory';
import './BenchmarkDiscovery.css';

interface Props {
	onPreview: (benchmark: Benchmark) => void;
}

const BenchmarkDiscovery: React.FC<Props> = ({ onPreview }) => {
	const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
	const [sectors, setSectors] = useState<string[]>([]);
	const [search, setSearch] = useState('');
	const [selectedSector, setSelectedSector] = useState('');
	const [loading, setLoading] = useState(true);
	const [selectedMetric, setSelectedMetric] = useState<{key: string, name: string} | null>(null);

	useEffect(() => {
		const fetchData = async () => {
			setLoading(true);
			try {
				const sectorParam = selectedSector ? `&sector=${encodeURIComponent(selectedSector)}` : '';
				const [benchRes, sectorRes] = await Promise.all([
					fetch(`http://localhost:8000/api/benchmarks?asset_type=STOCK${sectorParam}`),
					fetch('http://localhost:8000/api/sectors')
				]);
				if (benchRes.ok) setBenchmarks(await benchRes.json());
				if (sectorRes.ok) setSectors(await sectorRes.json());
			} catch (error) {
				console.error('Error fetching data:', error);
			} finally {
				setLoading(false);
			}
		};
		fetchData();
	}, [selectedSector]);

	const filteredBenchmarks = benchmarks.filter(b => {
		const matchesSearch = b.name.toLowerCase().includes(search.toLowerCase()) || 
							  b.metric.toLowerCase().includes(search.toLowerCase());
		return matchesSearch;
	});

	if (loading) return <div className="loading">Loading Benchmarks...</div>;

	return (
		<div className="discovery-container">
			<header className="discovery-header">
				<div className="search-bar">
					<Search size={18} />
					<input 
						type="text" 
						placeholder="Search metrics (e.g. P/E, Growth)..." 
						value={search}
						onChange={(e) => setSearch(e.target.value)}
					/>
				</div>
				<div className="sector-filter">
					<Filter size={18} />
					<select 
						value={selectedSector} 
						onChange={(e) => setSelectedSector(e.target.value)}
					>
						<option value="">Global Benchmarks</option>
						{sectors.map(s => <option key={s} value={s}>{s}</option>)}
					</select>
				</div>
			</header>

			<div className="benchmark-grid">
				<table>
					<thead>
						<tr>
							<th>Metric Name</th>
							<th>Key</th>
							<th>Type</th>
							<th>Weight</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody>
						{filteredBenchmarks.map(b => (
							<tr 
								key={b.metric}
								className={selectedMetric?.key === b.metric ? 'selected-row' : ''}
								onClick={() => setSelectedMetric({key: b.metric, name: b.name})}
							>
								<td className="metric-name">{b.name}</td>
								<td className="metric-key"><code>{b.metric}</code></td>
								<td><span className={`badge ${b.type}`}>{b.type}</span></td>
								<td>{b.weight.toFixed(1)}x</td>
								<td>
									<div className="action-buttons">
										<button 
											className="preview-btn"
											onClick={(e) => {
												e.stopPropagation();
												onPreview(b);
											}}
											title="Preview in Math Explorer"
										>
											<Play size={14} fill="currentColor" /> Preview
										</button>
										<button 
											className={`history-btn ${selectedMetric?.key === b.metric ? 'active' : ''}`}
											onClick={(e) => {
												e.stopPropagation();
												setSelectedMetric(selectedMetric?.key === b.metric ? null : {key: b.metric, name: b.name});
											}}
											title="View History"
										>
											<BarChart2 size={14} /> History
										</button>
									</div>
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>

			{selectedMetric && (
				<MetricHistory 
					metricKey={selectedMetric.key} 
					metricName={selectedMetric.name} 
				/>
			)}
		</div>
	);
};

export default BenchmarkDiscovery;
