import { useState, useEffect, useCallback } from 'react'
import { API_BASE_URL } from '../config'

let cache: string[] | null = null
let pending: Promise<string[]> | null = null

function fetchProfiles(): Promise<string[]> {
	if (!pending) {
		pending = fetch(`${API_BASE_URL}/api/profiles/list`)
			.then(r => r.ok ? r.json() : [])
			.then(data => { cache = data; return data as string[] })
			.catch(() => { pending = null; return [] })
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
 * @returns refetch  - invalidates the cache and re-fetches from the server
 */
export function useProfiles() {
	const [profiles, setProfiles] = useState<string[]>(cache ?? [])
	const [loading, setLoading] = useState(cache === null)

	useEffect(() => {
		if (cache !== null) {
			setProfiles(cache)
			setLoading(false)
			return
		}
		setLoading(true)
		fetchProfiles().then(data => {
			setProfiles(data)
			setLoading(false)
		})
	}, [])

	const refetch = useCallback(() => {
		cache = null
		pending = null
		setLoading(true)
		fetchProfiles().then(data => {
			setProfiles(data)
			setLoading(false)
		})
	}, [])

	return { profiles, loading, refetch }
}
