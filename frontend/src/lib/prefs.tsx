import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

/**
 * Display preferences and text-to-speech.
 *
 * Stored per-browser rather than only on the profile, so they work before
 * sign-in too -- someone who needs large text needs it on the login screen.
 */

type Prefs = {
  largeText: boolean
  highContrast: boolean
  setLargeText: (value: boolean) => void
  setHighContrast: (value: boolean) => void
  speak: (text: string, language: 'en' | 'ne') => void
  stopSpeaking: () => void
  speaking: boolean
  speechSupported: boolean
}

const PrefsContext = createContext<Prefs | null>(null)
const STORAGE_KEY = 'sahayatri.prefs'

function readStored(): { largeText: boolean; highContrast: boolean } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return {
        largeText: Boolean(parsed.largeText),
        highContrast: Boolean(parsed.highContrast),
      }
    }
  } catch {
    // Corrupt or unavailable storage: fall back to defaults.
  }
  return { largeText: false, highContrast: false }
}

export function PrefsProvider({ children }: { children: ReactNode }) {
  const initial = readStored()
  const [largeText, setLargeTextState] = useState(initial.largeText)
  const [highContrast, setHighContrastState] = useState(initial.highContrast)
  const [speaking, setSpeaking] = useState(false)

  const speechSupported =
    typeof window !== 'undefined' && 'speechSynthesis' in window

  useEffect(() => {
    const root = document.documentElement
    root.toggleAttribute('data-large-text', largeText)
    root.toggleAttribute('data-high-contrast', highContrast)

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ largeText, highContrast }))
    } catch {
      // Preference just will not persist.
    }
  }, [largeText, highContrast])

  // Stop any narration when the tab closes, otherwise it keeps talking.
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  const stopSpeaking = useCallback(() => {
    if (!speechSupported) return
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [speechSupported])

  const speak = useCallback(
    (text: string, language: 'en' | 'ne') => {
      if (!speechSupported || !text.trim()) return

      window.speechSynthesis.cancel()

      const utterance = new SpeechSynthesisUtterance(text)

      // Nepali TTS voices are rare. Prefer ne-NP, fall back to Hindi (same
      // script, largely intelligible), then whatever the browser has. If none
      // of it works the button simply does nothing rather than erroring.
      const voices = window.speechSynthesis.getVoices()
      const preferred =
        language === 'ne'
          ? voices.find((v) => v.lang.startsWith('ne')) ??
            voices.find((v) => v.lang.startsWith('hi'))
          : voices.find((v) => v.lang.startsWith('en'))

      if (preferred) utterance.voice = preferred
      utterance.lang = preferred?.lang ?? (language === 'ne' ? 'ne-NP' : 'en-US')
      utterance.rate = 0.95

      utterance.onend = () => setSpeaking(false)
      utterance.onerror = () => setSpeaking(false)

      setSpeaking(true)
      window.speechSynthesis.speak(utterance)
    },
    [speechSupported],
  )

  const value = useMemo<Prefs>(
    () => ({
      largeText,
      highContrast,
      setLargeText: setLargeTextState,
      setHighContrast: setHighContrastState,
      speak,
      stopSpeaking,
      speaking,
      speechSupported,
    }),
    [largeText, highContrast, speak, stopSpeaking, speaking, speechSupported],
  )

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>
}

export function usePrefs(): Prefs {
  const context = useContext(PrefsContext)
  if (!context) throw new Error('usePrefs must be used inside PrefsProvider')
  return context
}
