import { useState, useEffect } from 'react'
import { API_BASE_URL } from '../config'
import { Activity, Database, Server, RefreshCw, AlertCircle, X, FileText, Copy, Check, Settings, Save } from 'lucide-react'
import './AdminDashboard.css'

interface AggregateStats {
	total_sessions: number;
	total_analyzed: number;
	total_cache_hits: number;
	total_api_attempts: number;
	total_errors: number;
	avg_duration_s: number;
	asset_counts: Record<string, number>;
}

interface TelemetryEntry {
	id: number;
	timestamp: string;
	duration_s: number;
	total_tickers: number;
	analyzed_tickers: number;
	cache_hits: number;
	api_attempts: number;
	errors: number;
	metrics_json: string;
}

interface AppSetting {
	key: string;
	value: string;
	category: string;
	description?: string;
	last_updated: string;
}

const AdminDashboard: React.FC = () => {
	const [activeSubTab, setActiveSubTab] = useState<'telemetry' | 'database' | 'settings'>('telemetry')
	const [tickersExpanded, setTickersExpanded] = useState(false)
	const [jsonCopied, setJsonCopied] = useState(false)

	const copyJson = (text: string) => {
		navigator.clipboard.writeText(text).then(() => {
			setJsonCopied(true)
			setTimeout(() => setJsonCopied(false), 2000)
		})
	}
	const [aggStats, setAggStats] = useState<AggregateStats | null>(null)
	const [telemetry, setTelemetry] = useState<TelemetryEntry[]>([])
	const [selectedEntry, setSelectedEntry] = useState<TelemetryEntry | null>(null)
	const [dbTable, setDbTable] = useState<string>('assets')
	const [dbData, setDbData] = useState<any[]>([])
	const [tables, setTables] = useState<string[]>([])
	const [settings, setSettings] = useState<AppSetting[]>([])
	const [editingSettings, setEditingSettings] = useState<Record<string, string>>({})
	const [currentLogLevel, setCurrentLogLevel] = useState<string>('INFO')
	const [isLoading, setIsLoading] = useState(false)
	const [savingKey, setSavingKey] = useState<string | null>(null)
	const [error, setError] = useState<string | null>(null)

	const isModified = (key: string) => editingSettings[key] !== settings.find(s => s.key === key)?.value
	const hasChanges = settings.some(s => isModified(s.key))

	const fetchAggStats = async () => {
		try {
			const res = await fetch(`${API_BASE_URL}/api/admin/stats`)
			if (res.ok) setAggStats(await res.json())
		} catch {
			// non-critical — silently skip if stats unavailable
		}
	}

	const fetchTables = async () => {
		try {
			const res = await fetch(`${API_BASE_URL}/api/admin/db/tables`)
			if (res.ok) {
				const data = await res.json()
				setTables(data)
				if (data.length > 0 && !data.includes(dbTable)) {
					setDbTable(data[0])
				}
			}
		} catch {
			// fallback to hardcoded if API fails
			setTables(['assets', 'indices', 'analysis_snapshots', 'global_benchmarks', 'sector_benchmarks', 'investor_profiles', 'groups', 'session_telemetry'])
		}
	}

	const fetchTelemetry = async () => {
		setIsLoading(true)
		setError(null)
		try {
			const res = await fetch(`${API_BASE_URL}/api/admin/telemetry`)
			if (res.ok) setTelemetry(await res.json())
			else setError('Failed to load telemetry')
		} catch (err) {
			setError('Network error loading telemetry')
		}
		setIsLoading(false)
	}

	const fetchDbData = async (table: string) => {
		setIsLoading(true)
		setError(null)
		try {
			const res = await fetch(`${API_BASE_URL}/api/admin/db/${table}`)
			if (res.ok) setDbData(await res.json())
			else setError(`Failed to load table: ${table}`)
		} catch (err) {
			setError('Network error loading database data')
		}
		setIsLoading(false)
	}

	const fetchSettings = async () => {
		setIsLoading(true)
		setError(null)
		try {
			const res = await fetch(`${API_BASE_URL}/api/admin/settings`)
			if (res.ok) {
				const data = await res.json()
				setSettings(data)
				// Initialize editing state
				const editing: Record<string, string> = {}
				data.forEach((s: AppSetting) => {
					editing[s.key] = s.value
				})
				setEditingSettings(editing)
			} else {
				setError('Failed to load settings')
			}
		} catch (err) {
			setError('Network error loading settings')
		}
		setIsLoading(false)
	}

	const saveAllSettings = async () => {
		setSavingKey('all')
		setError(null)
		try {
			const toUpdate = settings.filter(s => isModified(s.key))

			for (const setting of toUpdate) {
				const res = await fetch(`${API_BASE_URL}/api/admin/settings/${setting.key}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ value: editingSettings[setting.key] })
				})
				if (!res.ok) throw new Error(`Failed to save ${setting.key}`)
			}

			await fetchSettings()
			await fetchLogLevel()
		} catch (err) {
			setError((err as Error).message || 'Failed to save some settings')
		} finally {
			setSavingKey(null)
		}
	}

	const fetchLogLevel = async () => {
		try {
			const res = await fetch(`${API_BASE_URL}/api/admin/log-level`)
			if (res.ok) {
				const data = await res.json()
				setCurrentLogLevel(data.level)
			}
		} catch {
			// ignore non-critical errors
		}
	}

	const selectLogLevel = (level: string) => {
		setCurrentLogLevel(level)
		setEditingSettings(prev => ({ ...prev, log_level: level }))
	}

	useEffect(() => {
		fetchAggStats()
		fetchTables()
		fetchLogLevel()
	}, [])

	useEffect(() => {
		if (activeSubTab === 'telemetry') fetchTelemetry()
		else if (activeSubTab === 'settings') {
			fetchSettings()
			fetchLogLevel()
		}
	}, [activeSubTab])

	useEffect(() => {
		if (activeSubTab === 'database' && dbTable) fetchDbData(dbTable)
	}, [activeSubTab, dbTable])

	return (
		<div className="admin-dashboard">
			<div className="admin-header">
				<div className="admin-title-row">
					<Server size={24} className="admin-icon" />
					<h1>System Administration</h1>
				</div>
				</div>

			{aggStats && (
				<div className="stats-cards">
					<div className="stat-card">
						<label>Sessions</label>
						<span>{aggStats.total_sessions}</span>
					</div>
					<div className="stat-card">
						<label>Tickers Analyzed</label>
						<span>{aggStats.total_analyzed.toLocaleString()}</span>
					</div>
					<div className="stat-card">
						<label>Cache Hits</label>
						<span className="text-green">{aggStats.total_cache_hits.toLocaleString()}</span>
					</div>
					<div className="stat-card">
						<label>API Fetches</label>
						<span className="text-cyan">{aggStats.total_api_attempts.toLocaleString()}</span>
					</div>
					<div className="stat-card">
						<label>Avg Duration</label>
						<span>{aggStats.avg_duration_s}s</span>
					</div>
					<div className="stat-card">
						<label>Errors</label>
						<span className={aggStats.total_errors > 0 ? 'text-red' : ''}>{aggStats.total_errors}</span>
					</div>
					{Object.entries(aggStats.asset_counts).map(([type, count]) => (
						<div key={type} className="stat-card">
							<label>{type || 'Unknown'}</label>
							<span>{count}</span>
						</div>
					))}
				</div>
			)}

			<div className="admin-nav">
				<button 
					className={`admin-nav-btn ${activeSubTab === 'telemetry' ? 'active' : ''}`}
					onClick={() => setActiveSubTab('telemetry')}
				>
					<Activity size={16} /> Telemetry
				</button>
				<button 
					className={`admin-nav-btn ${activeSubTab === 'database' ? 'active' : ''}`}
					onClick={() => setActiveSubTab('database')}
				>
					<Database size={16} /> Database Explorer
				</button>
				<button 
					className={`admin-nav-btn ${activeSubTab === 'settings' ? 'active' : ''}`}
					onClick={() => setActiveSubTab('settings')}
				>
					<Settings size={16} /> System Settings
				</button>
			</div>

			{error && (
				<div className="admin-error">
					<AlertCircle size={16} /> {error}
				</div>
			)}

			<div className="admin-content">
				{isLoading ? (
					<div className="admin-loading">
						<RefreshCw size={24} className="spin" />
						<span>Fetching system data...</span>
					</div>
				) : activeSubTab === 'telemetry' ? (
					<div className="telemetry-view">
						<div className="section-header">
							<h3>Recent Session Telemetry</h3>
							<button className="refresh-btn" onClick={fetchTelemetry}>
								<RefreshCw size={14} /> Refresh
							</button>
						</div>
						<div className="admin-table-container">
							<table className="admin-table">
								<thead>
									<tr>
										<th>ID</th>
										<th>Timestamp</th>
										<th>Duration</th>
										<th>Tickers</th>
										<th>Analyzed</th>
										<th>Cache</th>
										<th>API</th>
										<th>Errors</th>
									</tr>
								</thead>
								<tbody>
									{telemetry.map(entry => (
										<tr 
											key={entry.id} 
											onClick={() => { setSelectedEntry(entry); setTickersExpanded(false); setJsonCopied(false) }}
											className="clickable-row"
											title="Click to view detailed metrics"
										>
											<td className="dim">{entry.id}</td>
											{/* SQLite CURRENT_TIMESTAMP is UTC — appending Z is correct */}
											<td>{new Date(entry.timestamp + 'Z').toLocaleString()}</td>
											<td>{entry.duration_s.toFixed(2)}s</td>
											<td>{entry.total_tickers}</td>
											<td className="bold">{entry.analyzed_tickers}</td>
											<td className="text-green">{entry.cache_hits}</td>
											<td className="text-cyan">{entry.api_attempts}</td>
											<td className={entry.errors > 0 ? 'text-red' : ''}>{entry.errors}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					</div>
				) : activeSubTab === 'database' ? (
					<div className="database-view">
						<div className="section-header">
							<div className="table-selector">
								<Database size={14} />
								<select value={dbTable} onChange={(e) => setDbTable(e.target.value)}>
									{tables.map(t => <option key={t} value={t}>{t}</option>)}
								</select>
							</div>
							<button className="refresh-btn" onClick={() => fetchDbData(dbTable)}>
								<RefreshCw size={14} /> Refresh
							</button>
						</div>
						<div className="admin-table-container">
							{dbData.length > 0 ? (
								<table className="admin-table">
									<thead>
										<tr>
											{Object.keys(dbData[0]).map(key => (
												<th key={key}>{key}</th>
											))}
										</tr>
									</thead>
									<tbody>
										{dbData.map((row, i) => (
											<tr key={i}>
												{Object.values(row).map((val: any, j) => (
													<td key={j} className={typeof val === 'number' ? 'mono text-right' : ''}>
														{typeof val === 'object' ? JSON.stringify(val) : String(val ?? 'NULL')}
													</td>
												))}
											</tr>
										))}
									</tbody>
								</table>
							) : (
								<div className="empty-state">No records found in this table.</div>
							)}
						</div>
					</div>
				) : (
					<div className="settings-view">
						<div className="section-header">
							<h3>Application Settings</h3>
							<button className="refresh-btn" onClick={() => { fetchSettings(); fetchLogLevel(); }}>
								<RefreshCw size={14} /> Refresh
							</button>
						</div>

						<div className="log-level-control">
							<label>Server Log Level</label>
							<div className="log-level-buttons">
								{['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map(level => (
									<button
										key={level}
										className={`log-level-btn ${currentLogLevel === level ? 'active' : ''}`}
										onClick={() => selectLogLevel(level)}
										disabled={savingKey === 'all'}
									>
										{level}
									</button>
								))}
							</div>
							<p className="dim small">Changes take effect immediately across the server process.</p>
						</div>

						<div className="admin-table-container">
							<table className="admin-table settings-table">
								<thead>
									<tr>
										<th>Category</th>
										<th>Setting Key</th>
										<th>Value</th>
										<th>Description</th>
									</tr>
								</thead>
								<tbody>
									{settings.filter(s => s.key !== 'log_level').map(setting => (
										<tr key={setting.key}>
											<td className="dim">{setting.category}</td>
											<td className="bold">{setting.key}</td>
											<td>
												<input 
													type="text" 
													className={`setting-input ${isModified(setting.key) ? 'modified' : ''}`}
													value={editingSettings[setting.key] || ''} 
													onChange={(e) => setEditingSettings({...editingSettings, [setting.key]: e.target.value})}
												/>
											</td>
											<td className="dim small">{setting.description}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>

						<div className="settings-footer">
							{hasChanges && <span className="changes-indicator">You have unsaved changes</span>}
							<button 
								className="save-all-btn" 
								onClick={saveAllSettings}
								disabled={!hasChanges || savingKey === 'all'}
							>
								{savingKey === 'all' ? <RefreshCw size={16} className="spin" /> : <Save size={16} />}
								{savingKey === 'all' ? 'Saving Changes...' : 'Save All Changes'}
							</button>
						</div>
					</div>
				)}
			</div>

			{selectedEntry && (
				<div className="modal-overlay" onClick={() => setSelectedEntry(null)}>
					<div className="modal-content" onClick={e => e.stopPropagation()}>
						<div className="modal-header">
							<div className="modal-title">
								<Activity size={18} className="text-cyan" />
								<h3>Session Details #{selectedEntry.id}</h3>
							</div>
							<button className="close-btn" onClick={() => setSelectedEntry(null)}>
								<X size={20} />
							</button>
						</div>
						<div className="modal-body">
							<div className="metrics-summary">
								<div className="summary-card">
									<label>Duration</label>
									<span>{selectedEntry.duration_s.toFixed(2)}s</span>
								</div>
								<div className="summary-card">
									<label>Analyzed</label>
									<span>{selectedEntry.analyzed_tickers} / {selectedEntry.total_tickers}</span>
								</div>
								<div className="summary-card">
									<label>Cache Rate</label>
									<span>{((selectedEntry.cache_hits / (selectedEntry.cache_hits + selectedEntry.api_attempts || 1)) * 100).toFixed(1)}%</span>
								</div>
							</div>
							{(() => {
							try {
								const parsed = JSON.parse(selectedEntry.metrics_json)
								const symbols: string[] = parsed.analyzed_symbols ?? []
								const rest = { ...parsed }
								delete rest.analyzed_symbols
								return (
									<>
										{symbols.length > 0 && (
											<div className="tickers-section">
												<button
													className="tickers-toggle"
													onClick={() => setTickersExpanded(e => !e)}
												>
													<span>Tickers Analyzed ({symbols.length})</span>
													<span className="tickers-chevron">{tickersExpanded ? '▲' : '▼'}</span>
												</button>
												{tickersExpanded && (
													<div className="tickers-chips">
														{symbols.map(s => (
															<span key={s} className="ticker-chip">{s}</span>
														))}
													</div>
												)}
											</div>
										)}
										<div className="json-viewer">
											<div className="json-header">
												<FileText size={14} />
												<span>Raw Metrics Payload</span>
												<button className="copy-json-btn" onClick={() => copyJson(JSON.stringify(rest, null, 2))} title="Copy to clipboard">
													{jsonCopied ? <Check size={13} className="text-green" /> : <Copy size={13} />}
												</button>
											</div>
											<pre>{JSON.stringify(rest, null, 2)}</pre>
										</div>
									</>
								)
							} catch {
								return (
									<div className="json-viewer">
										<div className="json-header"><FileText size={14} /><span>Raw Metrics Payload</span></div>
										<pre>{selectedEntry.metrics_json ?? '(no metrics)'}</pre>
									</div>
								)
							}
						})()}
						</div>
					</div>
				</div>
			)}
		</div>
	)
}

export default AdminDashboard
