import { useState, useEffect } from 'react'
import './App.css'
import ScoringExplorer from './components/ScoringExplorer'
import BenchmarkDiscovery from './components/BenchmarkDiscovery'
import DataFetcher from './components/DataFetcher'
import AnalysisPanel from './components/AnalysisPanel'
import type { Benchmark } from './types'

function App() {
	const [backendStatus, setBackendStatus] = useState<'online' | 'offline'>('offline')
	const [activeTab, setActiveTab] = useState<'status' | 'math' | 'benchmarks' | 'fetcher' | 'analysis'>('status')
	const [previewBenchmark, setPreviewBenchmark] = useState<Benchmark | undefined>(undefined)

	useEffect(() => {
		const checkStatus = async () => {
			try {
				const response = await fetch('http://localhost:8000/api/status')
				if (response.ok) {
					setBackendStatus('online')
				} else {
					setBackendStatus('offline')
				}
			} catch (_error) {
				setBackendStatus('offline')
			}
		}

		checkStatus()
		const interval = setInterval(checkStatus, 5000)
		return () => clearInterval(interval)
	}, [])

	const handlePreview = (benchmark: Benchmark) => {
		setPreviewBenchmark(benchmark)
		setActiveTab('math')
	}

	return (
		<div className="equiquant-app">
			<header className="app-header">
				<div className="header-left-slot">
					{activeTab !== 'status' ? (
						<button className="logo-link" onClick={() => setActiveTab('status')}>
							<img src="/logo.png" className="logo" alt="EquiQuant logo" />
						</button>
					) : (
						<div className="hero-branding">
							<img src="/logo.png" className="logo logo-large" alt="EquiQuant logo" />
							<h1 className="logo-title-large">EquiQuant</h1>
						</div>
					)}
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
						className={activeTab === 'fetcher' ? 'active' : ''} 
						onClick={() => setActiveTab('fetcher')}
					>
						Data Fetcher
					</button>
					<button 
						className={activeTab === 'benchmarks' ? 'active' : ''} 
						onClick={() => setActiveTab('benchmarks')}
					>
						Benchmarks
					</button>
					<button 
						className={activeTab === 'math' ? 'active' : ''} 
						onClick={() => setActiveTab('math')}
					>
						Math Explorer
					</button>
				</nav>

				<div className="header-right-slot" />
			</header>

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

			{activeTab === 'fetcher' && (
				<section className="fetcher-section">
					<DataFetcher />
				</section>
			)}

			{activeTab === 'benchmarks' && (
				<section className="benchmarks-section">
					<BenchmarkDiscovery onPreview={handlePreview} />
				</section>
			)}

			{activeTab === 'math' && (
				<section className="math-section">
					<h2>Scoring Function Explorer</h2>
					<p className="section-desc">Visualize how raw financial metrics are mapped to percentage scores.</p>
					<ScoringExplorer initialData={previewBenchmark} />
				</section>
			)}

			{activeTab === 'analysis' && (
				<section className="analysis-section">
					<AnalysisPanel />
				</section>
			)}

			{activeTab === 'status' && (
				<footer className="app-footer">
					<div className="footer-status">
						<span className={`dot ${backendStatus}`}></span>
						<span className="status-text">
							{backendStatus === 'online' 
								? 'Backend Connected (localhost:8000)' 
								: 'Backend Offline (localhost:8000)'}
						</span>
					</div>
					<div className="footer-version">v0.1.0-alpha</div>
				</footer>
			)}
		</div>
	)
}

export default App
