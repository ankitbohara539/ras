"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Toaster } from "sonner";
import { AuthProvider } from "@/features/auth/auth-context";
import { PublicLanguageProvider } from "@/features/i18n/public-language";
import { ReadingPreferencesProvider } from "@/features/preferences/reading-preferences";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 20_000, refetchOnWindowFocus: false, retry: 1 },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <PublicLanguageProvider>
        <AuthProvider>
          <ReadingPreferencesProvider>
            {children}
            <Toaster richColors position="top-right" />
          </ReadingPreferencesProvider>
        </AuthProvider>
      </PublicLanguageProvider>
    </QueryClientProvider>
  );
}
