import React, { useState } from 'react';
import { API_BASE_URL } from '../config';
import './DataFetcher.css';

const DataFetcher: React.FC = () => {
	const [tickers, setTickers] = useState('');
	const [provider, setProvider] = useState('openbb');
	const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
	const [message, setMessage] = useState('');

	const handleFetch = async () => {
		if (!tickers.trim()) {
			setStatus('error');
			setMessage('Please enter at least one ticker.');
			return;
		}

		setStatus('loading');
		setMessage('');

		const tickerList = tickers.split(',').map(t => t.trim()).filter(t => t);

		try {
			const response = await fetch(`${API_BASE_URL}/api/fetch`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					tickers: tickerList,
					provider: provider,
				}),
			});

			const data = await response.json();

			if (response.ok && data.status === 'success') {
				setStatus('success');
				setMessage(data.message || 'Data fetched successfully!');
			} else {
				setStatus('error');
				setMessage(data.message || 'Failed to fetch data.');
			}
		} catch (error) {
			setStatus('error');
			setMessage('Error connecting to backend.');
		}
	};

	return (
		<div className="fetcher-container">
			<div className="fetcher-card">
				<h3>Market Data Fetcher</h3>
				<p className="fetcher-desc">Enter ticker symbols separated by commas to download fresh market data.</p>
				
				<div className="form-group">
					<label htmlFor="tickers">Ticker Symbols (e.g. AAPL, MSFT, TSLA)</label>
					<textarea 
						id="tickers"
						value={tickers}
						onChange={(e) => setTickers(e.target.value)}
						placeholder="AAPL, MSFT, GOOGL..."
						rows={4}
					/>
				</div>

				<div className="form-row">
					<div className="form-group">
						<label htmlFor="provider">Data Provider</label>
						<select 
							id="provider" 
							value={provider} 
							onChange={(e) => setProvider(e.target.value)}
						>
							<option value="openbb">OpenBB (Default)</option>
							<option value="nasdaq" disabled>Nasdaq Data Link (Coming Soon)</option>
						</select>
					</div>
					
					<button 
						className={`fetch-button ${status === 'loading' ? 'loading' : ''}`}
						onClick={handleFetch}
						disabled={status === 'loading'}
					>
						{status === 'loading' ? 'Fetching...' : 'Fetch Data'}
					</button>
				</div>

				{message && (
					<div className={`status-message ${status}`}>
						{message}
					</div>
				)}
			</div>

			<div className="fetcher-info">
				<h4>How it works</h4>
				<ul>
					<li>Data is fetched from standardized institutional providers.</li>
					<li>Results are cached locally for 3 hours or until the next market close.</li>
					<li>This process is separate from analysis, allowing you to build your local data lake first.</li>
				</ul>
			</div>
		</div>
	);
};

export default DataFetcher;
