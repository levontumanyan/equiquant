import { useState, useEffect, useCallback } from 'react'
import { API_BASE_URL } from '../config'

let cache: string[] | null = null
let pending: Promise<string[]> | null = null

function fetchFormulas(): Promise<string[]> {
	if (!pending) {
		pending = fetch(`${API_BASE_URL}/api/formulas`)
			.then(r => r.ok ? r.json() : [])
			.then(data => { cache = data; return data as string[] })
			.catch(() => { pending = null; return [] })
	}
	return pending
}

/**
 * Shared hook for the available scoring formula types.
 *
 * Module-level promise cache deduplicates concurrent mounts (ProfileBuilder +
 * ScoringStudio both consume this endpoint). Formulas are static config —
 * `refetch` is provided for completeness but rarely needed.
 *
 * @returns formulas - list of formula type strings (e.g. "sigmoid", "linear")
 * @returns loading  - true while the initial fetch is in flight
 * @returns refetch  - invalidates the cache and re-fetches from the server
 */
export function useFormulas() {
	const [formulas, setFormulas] = useState<string[]>(cache ?? [])
	const [loading, setLoading] = useState(cache === null)

	useEffect(() => {
		if (cache !== null) {
			setFormulas(cache)
			setLoading(false)
			return
		}
		setLoading(true)
		fetchFormulas().then(data => {
			setFormulas(data)
			setLoading(false)
		})
	}, [])

	const refetch = useCallback(() => {
		cache = null
		pending = null
		setLoading(true)
		fetchFormulas().then(data => {
			setFormulas(data)
			setLoading(false)
		})
	}, [])

	return { formulas, loading, refetch }
}
