import React, { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import type { AssetAnalysis } from '../types'
import WaterfallChart from './WaterfallChart'
import './ScoreWaterfallModal.css'

interface ScoreWaterfallModalProps {
	asset: AssetAnalysis | null
	onClose: () => void
	scoringContext?: 'global' | 'sector' | 'batch'
}

const CONTEXT_LABEL: Record<string, string> = {
	global: 'Global',
	sector: 'Sector-Relative',
	batch: 'Batch-Relative',
}

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

const ScoreWaterfallModal: React.FC<ScoreWaterfallModalProps> = ({ asset, onClose, scoringContext = 'global' }) => {
	const modalRef = useRef<HTMLDivElement>(null)
	const closeBtnRef = useRef<HTMLButtonElement>(null)

	// Fix 4: auto-focus close button when modal opens
	useEffect(() => {
		if (asset) closeBtnRef.current?.focus()
	}, [asset])

	// Fix 4: Escape to close + focus trap (Tab cycles within modal)
	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			if (e.key === 'Escape') { onClose(); return }
			if (e.key !== 'Tab' || !modalRef.current) return

			const focusable = Array.from(
				modalRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)
			).filter(el => !el.hasAttribute('disabled'))

			if (focusable.length === 0) return
			const first = focusable[0]
			const last = focusable[focusable.length - 1]

			if (e.shiftKey) {
				if (document.activeElement === first) { e.preventDefault(); last.focus() }
			} else {
				if (document.activeElement === last) { e.preventDefault(); first.focus() }
			}
		}
		window.addEventListener('keydown', handler)
		return () => window.removeEventListener('keydown', handler)
	}, [onClose])

	if (!asset) return null

	const scoreClass = asset.score >= 70 ? 'wf-score-high' : asset.score >= 40 ? 'wf-score-medium' : 'wf-score-low'

	return (
		<div className="wf-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label={`Score breakdown for ${asset.symbol}`}>
			<div className="wf-modal" ref={modalRef} onClick={e => e.stopPropagation()}>
				<div className="wf-modal-header">
					<div className="wf-modal-title">
						<span className="wf-symbol">{asset.symbol}</span>
						<span className="wf-asset-name">{asset.name}</span>
						<span className={`wf-score-badge ${scoreClass}`}>{asset.score.toFixed(1)} / 100</span>
						{scoringContext !== 'global' && (
							<span className={`wf-context-badge wf-context-${scoringContext}`}>
								{CONTEXT_LABEL[scoringContext]}
							</span>
						)}
					</div>
					<button ref={closeBtnRef} className="wf-close-btn" onClick={onClose} aria-label="Close breakdown">
						<X size={16} />
					</button>
				</div>

				<div className="wf-modal-body">
					<p className="wf-subtitle">
						Each bar shows how much a metric contributed to the final score. Hover for details.
					</p>
					<WaterfallChart results={asset.results} totalScore={asset.score} />
					<div className="wf-legend">
						<span className="wf-legend-item">
							<span className="wf-dot" style={{ background: '#22c55e' }} />
							Strong (&gt;7 pts)
						</span>
						<span className="wf-legend-item">
							<span className="wf-dot" style={{ background: '#86efac' }} />
							Good (3–7 pts)
						</span>
						<span className="wf-legend-item">
							<span className="wf-dot" style={{ background: '#fbbf24' }} />
							Weak (1–3 pts)
						</span>
						<span className="wf-legend-item">
							<span className="wf-dot" style={{ background: '#6b7280' }} />
							Minimal (&lt;1 pt)
						</span>
						<span className="wf-legend-item">
							<span className="wf-dot" style={{ background: '#3b82f6' }} />
							Total
						</span>
					</div>
				</div>
			</div>
		</div>
	)
}

export default ScoreWaterfallModal
