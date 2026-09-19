import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react'

/**
 * A small stale-while-revalidate cache for API reads.
 *
 * The point is speed without lying. With the database a network hop away,
 * every page used to open on a spinner. Now a page you have seen recently
 * paints instantly from memory -- and is refreshed in the same breath. The
 * rules that keep that honest:
 *
 *  - Always revalidate. Cached data is a first paint, never the answer: a
 *    fresh fetch starts as soon as a page mounts, unless the data is only
 *    seconds old (just prefetched, or just loaded by another component).
 *  - Nothing old is shown. Past MAX_SHOW_AGE a cached entry is not painted
 *    at all; the page shows its spinner as it always did.
 *  - Your own changes win. Any successful write (see api.ts) drops every
 *    cached read, so nothing shows data from before something you did.
 *    Pages on screen keep what they show and refetch at once.
 *  - One account's data never reaches another: sign-in and sign-out clear it.
 *  - Refetch when the tab regains focus, so a phone picked up after an hour
 *    catches up by itself.
 *
 * Keys starting with "ref:" are reference data (categories, wards) that is
 * the same for everyone and changes only on reseed; writes do not drop it.
 */

type Entry = {
  data?: unknown
  error?: unknown
  updatedAt: number
  // When the last fetch failed; auto-revalidation backs off after a failure
  // instead of retrying in a tight loop.
  failedAt?: number
  // A write happened since this was fetched: still shown, but refetched.
  invalidated?: boolean
  promise?: Promise<unknown>
  // Mounted components currently showing this key.
  watchers: number
}

// Beyond this, cached data is too old to paint; show a spinner instead.
const MAX_SHOW_AGE_MS = 2 * 60_000
// Data this recent is used as-is, without an immediate refetch.
const DEFAULT_FRESH_MS = 5_000
const RETRY_AFTER_ERROR_MS = 10_000

const store = new Map<string, Entry>()
const listeners = new Set<() => void>()
let version = 0
// Bumped by every write. A response to a request sent before the write may
// describe the world before it, so it is stored but marked for refetch.
let generation = 0

function emit() {
  version += 1
  listeners.forEach((listener) => listener())
}

function entry(key: string): Entry {
  let found = store.get(key)
  if (!found) {
    found = { updatedAt: 0, watchers: 0 }
    store.set(key, found)
  }
  return found
}

/** Fetch into the cache, sharing any request already in flight for the key. */
export function fetchQuery<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const current = entry(key)
  if (current.promise) return current.promise as Promise<T>

  const startedIn = generation
  const promise = fetcher()
    .then((data) => {
      const e = entry(key)
      e.data = data
      e.error = undefined
      e.failedAt = undefined
      e.updatedAt = Date.now()
      e.invalidated = startedIn !== generation
      return data
    })
    .catch((error) => {
      const e = entry(key)
      e.error = error
      e.failedAt = Date.now()
      throw error
    })
    .finally(() => {
      const e = store.get(key)
      if (e && e.promise === promise) e.promise = undefined
      emit()
    })

  current.promise = promise
  emit()
  return promise
}

/**
 * Warm the cache for a page the user is about to open (hover, focus, touch).
 * Skipped when the data is already fresh.
 */
export function prefetch<T>(key: string, fetcher: () => Promise<T>, freshMs = 15_000): void {
  const current = store.get(key)
  if (current?.promise) return
  if (current && current.data !== undefined && Date.now() - current.updatedAt < freshMs) return
  fetchQuery(key, fetcher).catch(() => {
    // A failed prefetch just means the page loads normally.
  })
}

/**
 * After a write: forget cached reads. Entries on screen are kept (so the page
 * does not flash empty) but marked stale, and their components refetch.
 */
export function invalidateAll({ keepReference = true } = {}): void {
  generation += 1
  for (const [key, e] of store) {
    if (keepReference && key.startsWith('ref:')) continue
    if (e.watchers > 0) {
      e.invalidated = true
    } else {
      store.delete(key)
    }
  }
  emit()
}

/** On sign-in / sign-out: nothing from the previous account survives. */
export function clearCache(): void {
  generation += 1
  store.clear()
  emit()
}

/**
 * Whether a mounted query for `key` should fetch now: nothing cached yet,
 * older than `freshMs`, or invalidated by a write -- and not already in
 * flight, or backing off after a failure.
 */
export function shouldRevalidate(key: string, freshMs = DEFAULT_FRESH_MS): boolean {
  const e = store.get(key)
  if (!e) return true
  if (e.promise) return false
  if (e.failedAt !== undefined && Date.now() - e.failedAt < RETRY_AFTER_ERROR_MS) return false
  return e.invalidated === true || Date.now() - e.updatedAt >= freshMs
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export type QueryState<T> = {
  data: T | undefined
  error: unknown
  /** No data to show yet: render a spinner. */
  loading: boolean
  /** Showing data while a fresher copy loads. */
  refreshing: boolean
  refetch: () => Promise<T | undefined>
}

/**
 * Read `key` through the cache. `key: null` disables the query (e.g. while
 * waiting for a location). Change the key when the inputs change.
 */
export function useQuery<T>(
  key: string | null,
  fetcher: () => Promise<T>,
  options: { freshMs?: number; refetchIntervalMs?: number } = {},
): QueryState<T> {
  const { freshMs = DEFAULT_FRESH_MS, refetchIntervalMs } = options
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  // Re-render whenever the store changes.
  useSyncExternalStore(subscribe, () => version)

  const current = key ? store.get(key) : undefined
  const age = current ? Date.now() - current.updatedAt : Infinity
  const showable = current?.data !== undefined && age < MAX_SHOW_AGE_MS

  const refetch = useCallback(async () => {
    if (!key) return undefined
    try {
      return await fetchQuery(key, () => fetcherRef.current())
    } catch {
      return undefined
    }
  }, [key])

  // Count watchers so invalidation knows what is on screen.
  useEffect(() => {
    if (!key) return
    const e = entry(key)
    e.watchers += 1
    return () => {
      e.watchers -= 1
    }
  }, [key])

  // Revalidate on mount / key change, and whenever the entry goes stale
  // (invalidated by a write while this component is showing it).
  const inFlight = Boolean(current?.promise)
  const needsFetch = key ? shouldRevalidate(key, freshMs) : false
  useEffect(() => {
    if (key && needsFetch) void refetch()
  }, [key, needsFetch, refetch])

  // Catch up when the tab comes back, and optionally on a timer.
  useEffect(() => {
    if (!key) return
    const onFocus = () => {
      if (document.visibilityState === 'visible') void refetch()
    }
    document.addEventListener('visibilitychange', onFocus)
    const timer = refetchIntervalMs ? window.setInterval(() => void refetch(), refetchIntervalMs) : null
    return () => {
      document.removeEventListener('visibilitychange', onFocus)
      if (timer) window.clearInterval(timer)
    }
  }, [key, refetch, refetchIntervalMs])

  return {
    data: showable ? (current!.data as T) : undefined,
    error: current?.error,
    loading: Boolean(key) && !showable && !current?.error,
    refreshing: showable && inFlight,
    refetch,
  }
}
