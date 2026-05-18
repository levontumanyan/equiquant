import { API_BASE_URL } from './config'
import { useState, useEffect } from 'react'
import './App.css'
import ScoringExplorer from './components/ScoringExplorer'
import ScoringStudio from './components/ScoringStudio'
import AnalysisPanel from './components/AnalysisPanel'
import AdminDashboard from './components/AdminDashboard'

function App() {
	const [backendStatus, setBackendStatus] = useState<'online' | 'offline'>('offline')
	const [openbbReady, setOpenbbReady] = useState<boolean | null>(null)
	const [activeTab, setActiveTab] = useState<'status' | 'math' | 'studio' | 'analysis' | 'admin'>('status')

	useEffect(() => {
		const handleNavigate = (e: any) => setActiveTab(e.detail)
		window.addEventListener('navigate', handleNavigate)
		return () => window.removeEventListener('navigate', handleNavigate)
	}, [])

	useEffect(() => {
		const checkStatus = async () => {
			try {
				const response = await fetch(`${API_BASE_URL}/api/status`)
				if (response.ok) {
					const data = await response.json()
					setBackendStatus('online')
					setOpenbbReady(data.openbb === 'ready')
				} else {
					setBackendStatus('offline')
					setOpenbbReady(false)
				}
			} catch (_error) {
				setBackendStatus('offline')
				setOpenbbReady(false)
			}
		}

		checkStatus()
		const interval = setInterval(checkStatus, 5000)
		return () => clearInterval(interval)
	}, [])

	return (
		<>
			<header className="app-header">
				<div className="header-left-slot">
					<button className="logo-link" onClick={() => setActiveTab('status')}>
						<img
							src="/logo.png"
							className={`logo${activeTab === 'status' ? ' logo-large' : ''}`}
							alt="EquiQuant logo"
						/>
						<span className={`logo-title${activeTab === 'status' ? ' logo-title-large' : ''}`}>
							EquiQuant
						</span>
					</button>
				</div>

				<nav className="app-nav">
					<button
						className={activeTab === 'status' ? 'active' : ''}
						onClick={() => setActiveTab('status')}
					>
						Status
					</button>
					<button
						className={activeTab === 'analysis' ? 'active' : ''}
						onClick={() => setActiveTab('analysis')}
					>
						Analysis
					</button>
					<button
						className={activeTab === 'studio' ? 'active' : ''}
						onClick={() => setActiveTab('studio')}
					>
						Studio
					</button>
					<button
						className={activeTab === 'math' ? 'active' : ''}
						onClick={() => setActiveTab('math')}
					>
						Functions
					</button>
					<button
						className={activeTab === 'admin' ? 'active' : ''}
						onClick={() => setActiveTab('admin')}
					>
						Admin
					</button>
				</nav>

				<div className="header-right-slot" />
			</header>

			<div className="equiquant-app">
				{activeTab === 'status' && (
					<div className="status-hero-container">
						<div className="card">
							{backendStatus === 'offline' && (
								<p className="connection-help">
									Run <code>make ui-server</code> to connect your local backend.
								</p>
							)}
							{backendStatus === 'online' && (
								<div className="welcome-hero">
									<button className="cta-button" onClick={() => setActiveTab('analysis')}>
										Get Started
									</button>
								</div>
							)}
						</div>
					</div>
				)}

				{activeTab === 'studio' && (
					<section className="studio-section">
						<ScoringStudio />
					</section>
				)}

				{activeTab === 'math' && (
					<section className="math-section">
						<h2>Scoring Functions</h2>
						<p className="section-desc">Visualize how raw financial metrics are mapped to percentage scores.</p>
						<ScoringExplorer />
					</section>
				)}

				{activeTab === 'analysis' && (
					<section className="analysis-section">
						<AnalysisPanel openbbReady={openbbReady} />
					</section>
				)}

				{activeTab === 'admin' && (
					<section className="admin-section">
						<AdminDashboard />
					</section>
				)}

				{activeTab === 'status' && (
					<footer className="app-footer">
						<div className="footer-status">
							<span className={`dot ${backendStatus}`}></span>
							<span className="status-text">
								{backendStatus === 'online' ? 'Backend Connected' : 'Backend Offline'}
							</span>
						</div>
						<div className="footer-version">v0.1.0-alpha</div>
					</footer>
				)}
			</div>
		</>
	)
}

export default App
