"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Square, Volume2 } from "lucide-react";
import { usePathname } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@/features/auth/auth-context";
import { api, patch } from "@/lib/api/client";

export type ReadingPreferences = {
  language: "en" | "ne";
  text_scale: "normal" | "large" | "x-large";
  high_contrast: boolean;
  reduced_motion: boolean;
  text_to_speech: boolean;
};

const defaults: ReadingPreferences = {
  language: "en",
  text_scale: "normal",
  high_contrast: false,
  reduced_motion: false,
  text_to_speech: false,
};

type ReadingPreferencesContextValue = {
  preferences: ReadingPreferences;
  loading: boolean;
  error: string | null;
  save: (preferences: ReadingPreferences) => Promise<ReadingPreferences>;
};

const ReadingPreferencesContext = createContext<ReadingPreferencesContextValue | null>(null);

function applyPreferences(preferences: ReadingPreferences, applyLanguage = true) {
  const root = document.documentElement;
  if (applyLanguage) root.lang = preferences.language;
  root.dataset.textScale = preferences.text_scale;
  root.dataset.highContrast = String(preferences.high_contrast);
  root.dataset.reducedMotion = String(preferences.reduced_motion);
}

export function ReadingPreferencesProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const queryKey = useMemo(
    () => ["users", user?.id, "reading-preferences"] as const,
    [user?.id],
  );
  const query = useQuery({
    queryKey,
    queryFn: () => api<ReadingPreferences>("/users/me/preferences"),
    enabled: Boolean(user),
    retry: 1,
  });
  const preferences = query.data ?? defaults;

  useEffect(() => {
    applyPreferences(user ? preferences : defaults, Boolean(user));
  }, [preferences, user]);

  const value = useMemo<ReadingPreferencesContextValue>(
    () => ({
      preferences,
      loading: authLoading || (Boolean(user) && query.isLoading),
      error: query.error instanceof Error ? query.error.message : null,
      save: async (next) => {
        const saved = await patch<ReadingPreferences>("/users/me/preferences", next);
        queryClient.setQueryData(queryKey, saved);
        applyPreferences(saved);
        return saved;
      },
    }),
    [authLoading, preferences, query.error, query.isLoading, queryClient, queryKey, user],
  );

  return (
    <ReadingPreferencesContext.Provider value={value}>
      {children}
      {user && preferences.text_to_speech && <SpeechControl language={preferences.language} />}
    </ReadingPreferencesContext.Provider>
  );
}

function SpeechControl({ language }: { language: ReadingPreferences["language"] }) {
  const pathname = usePathname();
  return <SpeechButton key={pathname} language={language} />;
}

function SpeechButton({ language }: { language: ReadingPreferences["language"] }) {
  const [speaking, setSpeaking] = useState(false);
  const supported =
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    "SpeechSynthesisUtterance" in window;

  useEffect(() => {
    return () => window.speechSynthesis?.cancel();
  }, []);

  if (!supported) return null;

  const toggle = () => {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const readable = document.querySelector<HTMLElement>("main");
    const text = readable?.innerText.trim();
    if (!text) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language === "ne" ? "ne-NP" : "en-US";
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  };

  return (
    <button
      type="button"
      className="speech-control"
      onClick={toggle}
      aria-label={speaking ? "Stop reading this page" : "Read this page aloud"}
      title={speaking ? "Stop reading" : "Read page aloud"}
    >
      {speaking ? <Square size={18} /> : <Volume2 size={20} />}
      <span>{speaking ? "Stop reading" : "Read page"}</span>
    </button>
  );
}

export function useReadingPreferences() {
  const context = useContext(ReadingPreferencesContext);
  if (!context) {
    throw new Error("useReadingPreferences must be used inside ReadingPreferencesProvider");
  }
  return context;
}
