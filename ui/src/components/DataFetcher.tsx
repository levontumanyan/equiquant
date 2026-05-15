import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../config';
import './DataFetcher.css';

interface Group {
	name: string;
	description: string | null;
	is_system: number;
}

const DataFetcher: React.FC = () => {
	const [tickers, setTickers] = useState('');
	const [provider, setProvider] = useState('openbb');
	const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
	const [message, setMessage] = useState('');

	const [groups, setGroups] = useState<Group[]>([]);
	const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
	const [showNewGroup, setShowNewGroup] = useState(false);
	const [newGroupName, setNewGroupName] = useState('');
	const [newGroupTickers, setNewGroupTickers] = useState('');
	const [newGroupDesc, setNewGroupDesc] = useState('');
	const [groupSaveStatus, setGroupSaveStatus] = useState<'idle' | 'saving' | 'error'>('idle');

	const loadGroups = useCallback(async () => {
		try {
			const res = await fetch(`${API_BASE_URL}/api/groups`);
			if (res.ok) setGroups(await res.json());
		} catch {}
	}, []);

	useEffect(() => { loadGroups(); }, [loadGroups]);

	const handleGroupClick = async (group: Group) => {
		if (selectedGroup === group.name) {
			setSelectedGroup(null);
			setTickers('');
			return;
		}
		setSelectedGroup(group.name);
		try {
			const res = await fetch(`${API_BASE_URL}/api/groups/${encodeURIComponent(group.name)}/tickers`);
			if (res.ok) {
				const tickerList: string[] = await res.json();
				setTickers(tickerList.join(', '));
			}
		} catch {}
	};

	const handleDeleteGroup = async (e: React.MouseEvent, groupName: string) => {
		e.stopPropagation();
		await fetch(`${API_BASE_URL}/api/groups/${encodeURIComponent(groupName)}`, { method: 'DELETE' });
		if (selectedGroup === groupName) {
			setSelectedGroup(null);
			setTickers('');
		}
		loadGroups();
	};

	const handleSaveGroup = async () => {
		const name = newGroupName.trim();
		const tickerList = newGroupTickers.split(',').map(t => t.trim()).filter(Boolean);
		if (!name || tickerList.length === 0) return;

		setGroupSaveStatus('saving');
		try {
			const params = new URLSearchParams({ name });
			if (newGroupDesc.trim()) params.set('description', newGroupDesc.trim());
			tickerList.forEach(t => params.append('tickers', t));

			const res = await fetch(`${API_BASE_URL}/api/groups?${params}`, { method: 'POST' });
			if (res.ok) {
				setNewGroupName('');
				setNewGroupTickers('');
				setNewGroupDesc('');
				setShowNewGroup(false);
				setGroupSaveStatus('idle');
				loadGroups();
			} else {
				setGroupSaveStatus('error');
			}
		} catch {
			setGroupSaveStatus('error');
		}
	};

	const handleFetch = async () => {
		if (!tickers.trim()) {
			setStatus('error');
			setMessage('Please enter at least one ticker.');
			return;
		}

		setStatus('loading');
		setMessage('');

		const tickerList = tickers.split(',').map(t => t.trim()).filter(Boolean);

		try {
			const response = await fetch(`${API_BASE_URL}/api/fetch`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ tickers: tickerList, provider }),
			});

			const data = await response.json();

			if (response.ok && data.status === 'success') {
				setStatus('success');
				setMessage(data.message || 'Data fetched successfully!');
			} else {
				setStatus('error');
				setMessage(data.message || 'Failed to fetch data.');
			}
		} catch {
			setStatus('error');
			setMessage('Error connecting to backend.');
		}
	};

	const systemGroups = groups.filter(g => g.is_system);
	const customGroups = groups.filter(g => !g.is_system);

	return (
		<div className="fetcher-container">
			<div className="fetcher-card">
				<h3>Market Data Fetcher</h3>
				<p className="fetcher-desc">Select a group or enter tickers manually to download fresh market data.</p>

				{/* Groups section */}
				<div className="groups-section">
					<div className="groups-header">
						<span className="groups-label">Groups</span>
						<button
							className="new-group-btn"
							onClick={() => setShowNewGroup(v => !v)}
						>
							{showNewGroup ? 'Cancel' : '+ New Group'}
						</button>
					</div>

					{showNewGroup && (
						<div className="new-group-form">
							<div className="new-group-fields">
								<input
									type="text"
									placeholder="Group name"
									value={newGroupName}
									onChange={e => setNewGroupName(e.target.value)}
									className="group-input"
								/>
								<input
									type="text"
									placeholder="Description (optional)"
									value={newGroupDesc}
									onChange={e => setNewGroupDesc(e.target.value)}
									className="group-input"
								/>
								<input
									type="text"
									placeholder="Tickers: AAPL, MSFT, GOOGL..."
									value={newGroupTickers}
									onChange={e => setNewGroupTickers(e.target.value)}
									className="group-input group-input--tickers"
								/>
							</div>
							<button
								className="save-group-btn"
								onClick={handleSaveGroup}
								disabled={groupSaveStatus === 'saving' || !newGroupName.trim() || !newGroupTickers.trim()}
							>
								{groupSaveStatus === 'saving' ? 'Saving...' : 'Save Group'}
							</button>
							{groupSaveStatus === 'error' && (
								<span className="group-save-error">Failed to save group.</span>
							)}
						</div>
					)}

					{groups.length > 0 && (
						<div className="groups-grid">
							{systemGroups.length > 0 && (
								<div className="group-row">
									{systemGroups.map(g => (
										<button
											key={g.name}
											className={`group-chip group-chip--system ${selectedGroup === g.name ? 'group-chip--active' : ''}`}
											onClick={() => handleGroupClick(g)}
											title={g.description ?? undefined}
										>
											<span className="group-chip-lock">★</span>
											<span className="group-chip-name">{g.name}</span>
										</button>
									))}
								</div>
							)}
							{customGroups.length > 0 && (
								<div className="group-row">
									{customGroups.map(g => (
										<button
											key={g.name}
											className={`group-chip ${selectedGroup === g.name ? 'group-chip--active' : ''}`}
											onClick={() => handleGroupClick(g)}
											title={g.description ?? undefined}
										>
											<span className="group-chip-name">{g.name}</span>
											<span
												className="group-chip-delete"
												onClick={e => handleDeleteGroup(e, g.name)}
												role="button"
												aria-label={`Delete ${g.name}`}
											>✕</span>
										</button>
									))}
								</div>
							)}
						</div>
					)}
				</div>

				{/* Ticker textarea */}
				<div className="form-group">
					<label htmlFor="tickers">
						Ticker Symbols
						{selectedGroup && (
							<span className="ticker-source"> — from <em>{selectedGroup}</em></span>
						)}
					</label>
					<textarea
						id="tickers"
						value={tickers}
						onChange={(e) => { setTickers(e.target.value); setSelectedGroup(null); }}
						placeholder="AAPL, MSFT, GOOGL..."
						rows={3}
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
					<li>Select a saved group or type tickers to populate the list.</li>
					<li>Data is fetched from standardized institutional providers and cached in SQLite.</li>
					<li>Custom groups are saved locally and persist across sessions.</li>
					<li>This step builds your local data lake independently of analysis runs.</li>
				</ul>
			</div>
		</div>
	);
};

export default DataFetcher;
