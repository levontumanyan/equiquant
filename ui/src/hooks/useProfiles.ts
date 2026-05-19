import { useState, useEffect, useCallback } from 'react'
import { API_BASE_URL } from '../config'

let cache: string[] | null = null
let pending: Promise<string[]> | null = null

function fetchProfiles(): Promise<string[]> {
	if (!pending) {
		pending = fetch(`${API_BASE_URL}/api/profiles/list`)
			.then(r => r.ok ? r.json() : Promise.reject(new Error('Failed to load profiles')))
			.then(data => { cache = data; return data as string[] })
			.catch(err => { pending = null; throw err })
	}
	return pending
}

/**
 * Shared hook for the profiles list endpoint.
 *
 * Module-level promise cache deduplicates concurrent mounts so only one
 * network request fires regardless of how many components call this hook.
 * Call `refetch()` after any mutation to invalidate and reload.
 *
 * @returns profiles - list of profile name strings
 * @returns loading  - true while the initial fetch is in flight
 * @returns error    - error message string if the fetch failed, otherwise null
 * @returns refetch  - invalidates the cache and re-fetches from the server
 */
export function useProfiles() {
	const [profiles, setProfiles] = useState<string[]>(cache ?? [])
	const [loading, setLoading] = useState(cache === null)
	const [error, setError] = useState<string | null>(null)

	useEffect(() => {
		if (cache !== null) {
			setProfiles(cache)
			setLoading(false)
			return
		}
		setLoading(true)
		fetchProfiles()
			.then(data => { setProfiles(data); setLoading(false) })
			.catch(err => { setError(err instanceof Error ? err.message : 'Failed to load profiles'); setLoading(false) })
	}, [])

	const refetch = useCallback(() => {
		cache = null
		pending = null
		setError(null)
		setLoading(true)
		fetchProfiles()
			.then(data => { setProfiles(data); setLoading(false) })
			.catch(err => { setError(err instanceof Error ? err.message : 'Failed to load profiles'); setLoading(false) })
	}, [])

	return { profiles, loading, error, refetch }
}
