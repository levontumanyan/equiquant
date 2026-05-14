import { useState, useEffect } from 'react'
import './App.css'
import ScoringExplorer from './components/ScoringExplorer'
import BenchmarkDiscovery from './components/BenchmarkDiscovery'
import type { Benchmark } from './types'

function App() {
	const [backendStatus, setBackendStatus] = useState<'online' | 'offline'>('offline')
	const [activeTab, setActiveTab] = useState<'status' | 'math' | 'benchmarks'>('status')
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
			} catch (error) {
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
			<nav className="app-nav">
				<button 
					className={activeTab === 'status' ? 'active' : ''} 
					onClick={() => setActiveTab('status')}
				>
					Status
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

			{activeTab === 'status' && (
				<>
					<div className="logo-container">
						<a href="https://github.com/levontumanyan/equiquant" target="_blank">
							<img src="/logo.png" className="logo" alt="EquiQuant logo" />
						</a>
					</div>
					
					<h1>EquiQuant</h1>

					<div className="card">
						<div className="status-indicator">
							<span className={`dot ${backendStatus}`}></span>
							<span>
								{backendStatus === 'online' 
									? 'Backend Connected (localhost:8000)' 
									: 'Backend Offline (localhost:8000)'}
							</span>
						</div>
						
						{backendStatus === 'offline' && (
							<p>
								Run <code>make ui-server</code> to connect your local backend.
							</p>
						)}
					</div>
					
					<p className="read-the-docs">
						Minimalistic Quantitative Analysis Dashboard
					</p>
				</>
			)}

			{activeTab === 'benchmarks' && (
				<section className="benchmarks-section">
					<h2>Benchmark Discovery</h2>
					<p className="section-desc">Browse and explore metrics defined in the system.</p>
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
		</div>
	)
}

export default App
