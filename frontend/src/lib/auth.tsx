import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, getToken, setToken } from './api'
import { clearCache } from './cache'
import type { Profile } from './types'

type AuthValue = {
  profile: Profile | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<Profile>
  signOut: () => void
  refresh: () => Promise<void>
  isAuthority: boolean
  isAdmin: boolean
  isCitizen: boolean
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore the session on boot. A stale token simply logs the user out
  // rather than leaving the app in a half-authenticated state.
  useEffect(() => {
    let cancelled = false

    async function restore() {
      if (!getToken()) {
        setLoading(false)
        return
      }
      try {
        const me = await api.me()
        if (!cancelled) setProfile(me)
      } catch {
        setToken(null)
        if (!cancelled) setProfile(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password)
    // Nothing cached for a previous account may be shown to this one.
    clearCache()
    setToken(result.access_token)
    // Login returns the durable profile fields. Hydrate once through /me so
    // private presentation fields such as the signed avatar URL are ready for
    // the sidebar immediately after sign-in.
    try {
      const hydrated = await api.me()
      setProfile(hydrated)
      return hydrated
    } catch {
      setProfile(result.profile)
      return result.profile
    }
  }, [])

  const signOut = useCallback(() => {
    clearCache()
    setToken(null)
    setProfile(null)
  }, [])

  const refresh = useCallback(async () => {
    try {
      setProfile(await api.me())
    } catch {
      setToken(null)
      setProfile(null)
    }
  }, [])

  const value = useMemo<AuthValue>(
    () => ({
      profile,
      loading,
      signIn,
      signOut,
      refresh,
      isAuthority: profile?.role === 'authority' || profile?.role === 'admin',
      isAdmin: profile?.role === 'admin',
      isCitizen: profile?.role === 'citizen',
    }),
    [profile, loading, signIn, signOut, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
