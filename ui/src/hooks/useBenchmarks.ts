import { useState, useEffect, useCallback } from 'react'
import { API_BASE_URL } from '../config'
import type { Benchmark } from '../types'

let cache: Benchmark[] | null = null
let pending: Promise<Benchmark[]> | null = null

function fetchBenchmarks(): Promise<Benchmark[]> {
	if (!pending) {
		pending = fetch(`${API_BASE_URL}/api/benchmarks?asset_type=STOCK`)
			.then(r => r.ok ? r.json() : Promise.reject(new Error('Failed to load benchmarks')))
			.then(data => { cache = data; return data as Benchmark[] })
			.catch(err => { pending = null; throw err })
	}
	return pending
}

/**
 * Shared hook for the full STOCK benchmarks list.
 *
 * Fetches all benchmarks once and caches at module scope — concurrent mounts
 * share a single in-flight request. Sector filtering should be done client-side
 * from the returned array, which avoids additional round-trips per sector change.
 *
 * @returns benchmarks - full list of Benchmark objects for asset_type=STOCK
 * @returns loading    - true while the initial fetch is in flight
 * @returns error      - error message string if the fetch failed, otherwise null
 * @returns refetch    - invalidates the cache and re-fetches from the server
 */
export function useBenchmarks() {
	const [benchmarks, setBenchmarks] = useState<Benchmark[]>(cache ?? [])
	const [loading, setLoading] = useState(cache === null)
	const [error, setError] = useState<string | null>(null)

	useEffect(() => {
		if (cache !== null) {
			setBenchmarks(cache)
			setLoading(false)
			return
		}
		setLoading(true)
		fetchBenchmarks()
			.then(data => { setBenchmarks(data); setLoading(false) })
			.catch(err => { setError(err instanceof Error ? err.message : 'Failed to load benchmarks'); setLoading(false) })
	}, [])

	const refetch = useCallback(() => {
		cache = null
		pending = null
		setError(null)
		setLoading(true)
		fetchBenchmarks()
			.then(data => { setBenchmarks(data); setLoading(false) })
			.catch(err => { setError(err instanceof Error ? err.message : 'Failed to load benchmarks'); setLoading(false) })
	}, [])

	return { benchmarks, loading, error, refetch }
}
