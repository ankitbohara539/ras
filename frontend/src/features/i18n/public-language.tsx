"use client";

import { Languages } from "lucide-react";
import { createContext, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";

export type PublicLanguage = "en" | "ne";

const storageKey = "civicgrid-public-language";
const changeEvent = "civicgrid-language-change";

function readLanguage(): PublicLanguage {
  return localStorage.getItem(storageKey) === "ne" ? "ne" : "en";
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(changeEvent, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(changeEvent, callback);
  };
}

type LanguageContextValue = {
  language: PublicLanguage;
  setLanguage: (language: PublicLanguage) => void;
  text: (english: string, nepali: string) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function PublicLanguageProvider({ children }: { children: ReactNode }) {
  const language = useSyncExternalStore(subscribe, readLanguage, () => "en" as const);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => ({
    language,
    setLanguage: (next) => {
      localStorage.setItem(storageKey, next);
      document.documentElement.lang = next;
      window.dispatchEvent(new Event(changeEvent));
    },
    text: (english, nepali) => language === "ne" ? nepali : english,
  }), [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function usePublicLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("usePublicLanguage must be used inside PublicLanguageProvider");
  return context;
}

export function PublicLanguageToggle({ compact = false }: { compact?: boolean }) {
  const { language, setLanguage } = usePublicLanguage();
  return (
    <div className={compact ? "language-toggle compact" : "language-toggle"} aria-label="Language selector">
      <Languages size={15} aria-hidden="true" />
      <button type="button" className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")} aria-pressed={language === "en"}>EN</button>
      <span>/</span>
      <button type="button" className={language === "ne" ? "active" : ""} onClick={() => setLanguage("ne")} aria-pressed={language === "ne"}>नेपाली</button>
    </div>
  );
}
