import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
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
  /** Read `text` aloud as the button `id`. Stops whatever else was playing. */
  speak: (text: string, id: string, language: 'en' | 'ne') => void
  /** Stop speech. With an id, only if that button is the one playing. */
  stopSpeaking: (id?: string) => void
  /** Which button is playing. One at a time, so only that one shows "stop". */
  speakingId: string | null
  /** Why the last attempt made no sound, for the button that tried. */
  speechIssue: { id: string; message: string } | null
  speechSupported: boolean
}

const PrefsContext = createContext<Prefs | null>(null)
const STORAGE_KEY = 'sahayatri.prefs'

// Chrome silently stops any single utterance after ~15 seconds, so long text
// is spoken as a queue of sentence-sized pieces.
const MAX_CHUNK = 180

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

/** Emoji are read out as "speaker high volume" or not at all; drop them. */
function cleanForSpeech(text: string): string {
  return text
    .replace(/\p{Extended_Pictographic}(️|‍\p{Extended_Pictographic})*/gu, ' ')
    .replace(/️/g, '')
    .replace(/\s+/g, ' ')
    .replace(/(\.\s*){2,}/g, '. ')
    .trim()
}

function splitIntoChunks(text: string): string[] {
  // Sentence ends, including the Devanagari danda.
  const sentences = text.split(/(?<=[.!?।])\s+/)
  const chunks: string[] = []
  let current = ''

  const pushLong = (piece: string) => {
    let rest = piece
    while (rest.length > MAX_CHUNK) {
      const cut = rest.lastIndexOf(' ', MAX_CHUNK)
      const at = cut > 40 ? cut : MAX_CHUNK
      chunks.push(rest.slice(0, at))
      rest = rest.slice(at).trim()
    }
    return rest
  }

  for (const sentence of sentences) {
    if ((current + ' ' + sentence).trim().length <= MAX_CHUNK) {
      current = (current + ' ' + sentence).trim()
      continue
    }
    if (current) chunks.push(current)
    current = pushLong(sentence)
  }
  if (current) chunks.push(current)
  return chunks
}

function pickVoice(
  voices: SpeechSynthesisVoice[],
  nepali: boolean,
): SpeechSynthesisVoice | undefined {
  if (nepali) {
    // Nepali TTS voices are rare. Hindi shares the script and is largely
    // intelligible, so it is the fallback.
    return (
      voices.find((v) => v.lang.toLowerCase().startsWith('ne')) ??
      voices.find((v) => v.lang.toLowerCase().startsWith('hi'))
    )
  }
  return (
    voices.find((v) => v.lang.toLowerCase().startsWith('en') && v.default) ??
    voices.find((v) => v.lang.toLowerCase().startsWith('en'))
  )
}

export function PrefsProvider({ children }: { children: ReactNode }) {
  const initial = readStored()
  const [largeText, setLargeTextState] = useState(initial.largeText)
  const [highContrast, setHighContrastState] = useState(initial.highContrast)
  const [speakingId, setSpeakingId] = useState<string | null>(null)
  const [speechIssue, setSpeechIssue] = useState<Prefs['speechIssue']>(null)

  // Every speak() bumps this. Callbacks from an older run -- the cancelled
  // utterance's onerror fires *after* the new one has started -- compare
  // against it and do nothing, instead of switching the new button off.
  const runRef = useRef(0)
  const speakingIdRef = useRef<string | null>(null)
  // Chrome garbage-collects an utterance nobody references, and then its
  // onend never fires and the button is stuck on "stop".
  const queueRef = useRef<SpeechSynthesisUtterance[]>([])
  const voicesRef = useRef<SpeechSynthesisVoice[]>([])

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

  // getVoices() is empty until the browser has loaded them, which on Chrome
  // is after first paint. Picking a voice from that empty list is why the
  // first tap used to be silent.
  useEffect(() => {
    if (!speechSupported) return
    const synth = window.speechSynthesis
    const load = () => {
      voicesRef.current = synth.getVoices()
    }
    load()
    synth.addEventListener('voiceschanged', load)
    return () => synth.removeEventListener('voiceschanged', load)
  }, [speechSupported])

  // Stop any narration when the tab closes, otherwise it keeps talking.
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  const setActive = useCallback((id: string | null) => {
    speakingIdRef.current = id
    setSpeakingId(id)
  }, [])

  const stopSpeaking = useCallback(
    (id?: string) => {
      if (!speechSupported) return
      if (id !== undefined && speakingIdRef.current !== id) return
      runRef.current += 1
      queueRef.current = []
      window.speechSynthesis.cancel()
      setActive(null)
    },
    [speechSupported, setActive],
  )

  const speak = useCallback(
    (text: string, id: string, language: 'en' | 'ne') => {
      if (!speechSupported) return
      const clean = cleanForSpeech(text)
      if (!clean) return

      const synth = window.speechSynthesis
      const run = ++runRef.current
      synth.cancel()
      setSpeechIssue(null)

      // Choose the voice from what the text is written in, not the UI
      // language: an English report read by a Hindi voice (or Nepali by an
      // English one) comes out as silence or gibberish.
      const nepali =
        /[ऀ-ॿ]/.test(clean) ||
        (language === 'ne' && !/[A-Za-z]/.test(clean))
      const voices = voicesRef.current.length ? voicesRef.current : synth.getVoices()
      const voice = pickVoice(voices, nepali)

      const utterances = splitIntoChunks(clean).map((chunk) => {
        const utterance = new SpeechSynthesisUtterance(chunk)
        if (voice) utterance.voice = voice
        utterance.lang = voice?.lang ?? (nepali ? 'hi-IN' : 'en-US')
        utterance.rate = 0.95
        return utterance
      })

      const fail = (message: string) => {
        if (runRef.current !== run) return
        queueRef.current = []
        setActive(null)
        setSpeechIssue({ id, message })
      }

      utterances.forEach((utterance, index) => {
        utterance.onend = () => {
          if (runRef.current !== run) return
          if (index === utterances.length - 1) {
            queueRef.current = []
            setActive(null)
          }
        }
        utterance.onerror = (event) => {
          // Our own cancel() reports as an error; that is not a failure.
          if (event.error === 'interrupted' || event.error === 'canceled') return
          fail(
            nepali
              ? 'No Nepali or Hindi voice is installed on this device.'
              : 'This device could not play the audio.',
          )
        }
      })

      queueRef.current = utterances
      setActive(id)

      // Chrome drops an utterance queued in the same tick as cancel(), and a
      // previous interrupted run can leave the engine paused. Give cancel()
      // a moment, un-pause, then queue.
      window.setTimeout(() => {
        if (runRef.current !== run) return
        synth.resume()
        utterances.forEach((utterance) => synth.speak(utterance))

        // Some browsers have no voice for the language at all and fire
        // neither onend nor onerror -- the button would sit on "stop" in
        // silence forever. If nothing has started, say so.
        window.setTimeout(() => {
          if (runRef.current !== run) return
          if (!synth.speaking && !synth.pending) {
            fail(
              nepali && !voice
                ? 'No Nepali or Hindi voice is installed on this device.'
                : 'This device could not play the audio.',
            )
          }
        }, 2000)
      }, 80)
    },
    [speechSupported, setActive],
  )

  const value = useMemo<Prefs>(
    () => ({
      largeText,
      highContrast,
      setLargeText: setLargeTextState,
      setHighContrast: setHighContrastState,
      speak,
      stopSpeaking,
      speakingId,
      speechIssue,
      speechSupported,
    }),
    [largeText, highContrast, speak, stopSpeaking, speakingId, speechIssue, speechSupported],
  )

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>
}

export function usePrefs(): Prefs {
  const context = useContext(PrefsContext)
  if (!context) throw new Error('usePrefs must be used inside PrefsProvider')
  return context
}
