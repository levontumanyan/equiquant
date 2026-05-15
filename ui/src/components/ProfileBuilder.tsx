import React, { useState, useEffect } from 'react';
import './ProfileBuilder.css';
import type { Profile } from '../types/profile';
import MetricSearch from './MetricSearch';

const AVAILABLE_METRICS = [
	{ key: 'pe_ratio', name: 'Trailing P/E Ratio' },
	{ key: 'forward_pe', name: 'Forward P/E Ratio' },
	{ key: 'peg_ratio', name: 'PEG Ratio' },
	{ key: 'price_to_book', name: 'Price to Book' },
	{ key: 'return_on_equity', name: 'Return on Equity' },
	{ key: 'profit_margin', name: 'Profit Margin' },
	{ key: 'debt_to_equity', name: 'Debt to Equity' },
	{ key: 'current_ratio', name: 'Current Ratio' },
	{ key: 'revenue_growth', name: 'Revenue Growth' },
	{ key: 'insider_ownership', name: 'Insider Ownership' },
	{ key: 'institution_ownership', name: 'Institutional Ownership' },
	{ key: 'dividend_yield', name: 'Dividend Yield' },
	{ key: 'recommendation_mean', name: 'Analyst Recommendation' },
	{ key: 'short_percent_of_float', name: 'Short % of Float' },
	{ key: 'days_to_cover', name: 'Short Ratio' },
	{ key: 'enterprise_to_ebitda', name: 'EV/EBITDA' },
	{ key: 'ebitda_margin', name: 'EBITDA Margin' },
	{ key: 'beta_3y_avg', name: 'Beta (3Y)' },
	{ key: 'trailing_pe', name: 'P/E Ratio' },
];

const ProfileBuilder: React.FC = () => {
	const [availableFormulas, setAvailableFormulas] = useState<string[]>([]);
	const [profile, setProfile] = useState<Profile>({
		name: 'Default Profile',
		weights: {
			pe_ratio: 50,
			price_to_book: 50,
		},
		ranges: {
			pe_ratio: { min: 0, max: 100 },
			price_to_book: { min: 0, max: 100 },
		},
		formulas: {
			pe_ratio: 'sigmoid',
			price_to_book: 'sigmoid',
		},
	});
	const [statusMessage, setStatusMessage] = useState<string>('');

	useEffect(() => {
		fetch('http://localhost:8000/api/formulas')
			.then(res => res.json())
			.then(data => setAvailableFormulas(data))
			.catch(err => console.error('Failed to fetch formulas:', err));
	}, []);

	const handleWeightChange = (metric: string, value: number) => {
		setProfile((prevProfile) => ({
			...prevProfile,
			weights: {
				...prevProfile.weights,
				[metric]: value,
			},
		}));
	};

	const handleRangeChange = (metric: string, type: 'min' | 'max', value: number) => {
		const validatedValue = type === 'min' ? Math.max(0, value) : value;
		setProfile((prevProfile) => ({
			...prevProfile,
			ranges: {
				...prevProfile.ranges,
				[metric]: {
					...prevProfile.ranges[metric],
					[type]: validatedValue,
				},
			},
		}));
	};

	const handleFormulaChange = (metric: string, formula: string) => {
		setProfile((prevProfile) => ({
			...prevProfile,
			formulas: {
				...prevProfile.formulas,
				[metric]: formula,
			},
		}));
	};

	const handleAddMetric = (metricKey: string) => {
		if (metricKey && !profile.weights.hasOwnProperty(metricKey)) {
			setProfile((prev) => ({
				...prev,
				weights: { ...prev.weights, [metricKey]: 50 },
				ranges: { ...prev.ranges, [metricKey]: { min: 0, max: 100 } },
				formulas: { ...prev.formulas, [metricKey]: 'sigmoid' },
			}));
		}
	};

	const handleRemoveMetric = (metricKey: string) => {
		const { [metricKey]: _, ...remainingWeights } = profile.weights;
		const { [metricKey]: __, ...remainingRanges } = profile.ranges;
		const { [metricKey]: ___, ...remainingFormulas } = profile.formulas;
		setProfile({ ...profile, weights: remainingWeights, ranges: remainingRanges, formulas: remainingFormulas });
	};

	const handleSaveProfile = async () => {
		try {
			const response = await fetch('http://localhost:8000/api/profiles', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(profile),
			});

			if (response.ok) {
				setStatusMessage('Profile saved successfully!');
			} else {
				setStatusMessage('Failed to save profile.');
			}
		} catch (error) {
			setStatusMessage('Error saving profile.');
		}
	};

	return (
		<div className="profile-builder">
			<h2>Investor Profile Builder</h2>
			<div className="profile-name">
				<label htmlFor="profile-name">Profile Name:</label>
				<input
					type="text"
					id="profile-name"
					value={profile.name}
					onChange={(e) => setProfile({ ...profile, name: e.target.value })}
				/>
			</div>
			<div className="weights">
				<h3>Metric Weights</h3>
				{Object.entries(profile.weights).map(([metricKey, weight]) => (
					<div className="weight-slider" key={metricKey}>
						<label htmlFor={metricKey}>{AVAILABLE_METRICS.find(m => m.key === metricKey)?.name || metricKey}:</label>
						<input
							type="number"
							value={profile.ranges[metricKey]?.min || 0}
							onChange={(e) => handleRangeChange(metricKey, 'min', parseInt(e.target.value, 10))}
							className="range-input"
						/>
						<input
							type="range"
							id={metricKey}
							min={profile.ranges[metricKey]?.min || 0}
							max={profile.ranges[metricKey]?.max || 100}
							value={weight}
							onChange={(e) => handleWeightChange(metricKey, parseInt(e.target.value, 10))}
						/>
						<input
							type="number"
							value={profile.ranges[metricKey]?.max || 100}
							onChange={(e) => handleRangeChange(metricKey, 'max', parseInt(e.target.value, 10))}
							className="range-input"
						/>
						<span className="weight-val">{weight}</span>
						<select 
							value={profile.formulas[metricKey] || 'sigmoid'}
							onChange={(e) => handleFormulaChange(metricKey, e.target.value)}
							className="formula-select"
						>
							{availableFormulas.map(f => <option key={f} value={f}>{f}</option>)}
						</select>
						<button className="info-btn" onClick={() => window.dispatchEvent(new CustomEvent('navigate', { detail: 'math' }))}>
							?
						</button>
						<button className="remove-metric" onClick={() => handleRemoveMetric(metricKey)}>
							&times;
						</button>
					</div>
				))}
			</div>
			<div className="add-metric">
				<MetricSearch
						availableMetrics={AVAILABLE_METRICS}
						selectedMetrics={Object.keys(profile.weights)}
						onAddMetric={handleAddMetric}
				/>
			</div>
			<button onClick={handleSaveProfile}>Save Profile</button>
			{statusMessage && <p className="status-message">{statusMessage}</p>}
		</div>
	);
};

export default ProfileBuilder;
