import { useState, useEffect } from 'react'
import './App.css'

function App() {
	const [backendStatus, setBackendStatus] = useState<'online' | 'offline'>('offline')
	const [refreshCount, setRefreshCount] = useState(0)

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

	return (
		<div className="equiquant-app">
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
				
				<button onClick={() => setRefreshCount((c) => c + 1)}>
					Refresh Data {refreshCount > 0 && `(${refreshCount})`}
				</button>
				
				{backendStatus === 'offline' && (
					<p>
						Run <code>make ui-server</code> to connect your local backend.
					</p>
				)}
			</div>
			
			<p className="read-the-docs">
				Minimalistic Quantitative Analysis Dashboard
			</p>
		</div>
	)
}

export default App
