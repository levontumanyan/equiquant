import { useState, useEffect, useMemo } from 'react'
import { API_BASE_URL } from '../config'

export interface Asset {
	symbol: string
	name: string
	sector: string | null
	asset_type: string | null
}

let cache: Asset[] | null = null
let pending: Promise<Asset[]> | null = null

function fetchAssets(): Promise<Asset[]> {
	if (!pending) {
		pending = fetch(`${API_BASE_URL}/api/assets`)
			.then(r => r.ok ? r.json() : Promise.reject(new Error('Failed to load assets')))
			.then(data => { cache = data; return data as Asset[] })
			.catch(err => { pending = null; throw err })
	}
	return pending
}

/**
 * Shared hook for the assets list.
 *
 * Module-level promise cache deduplicates concurrent mounts so only one
 * network request fires regardless of how many components call this hook.
 *
 * @returns assets      - full list of assets
 * @returns filterAssets - convenience function: filters by symbol/name query, caps at maxResults
 */
export function useAssets() {
	const [assets, setAssets] = useState<Asset[]>(cache ?? [])

	useEffect(() => {
		if (cache !== null) { setAssets(cache); return }
		fetchAssets()
			.then(setAssets)
			.catch(() => {})
	}, [])

	const filterAssets = useMemo(() => (query: string, maxResults = 8): Asset[] => {
		if (!query) return []
		const q = query.toUpperCase()
		return assets
			.filter(a => a.symbol.includes(q) || (a.name ?? '').toUpperCase().includes(q))
			.slice(0, maxResults)
	}, [assets])

	return { assets, filterAssets }
}
