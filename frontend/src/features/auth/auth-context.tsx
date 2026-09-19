"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";
import { api, ApiError, post } from "@/lib/api/client";
import type { CurrentUser, Role } from "@/types";

type LoginInput = { email: string; password: string };
type RegisterInput = {
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
};

type AuthContextValue = {
  user: CurrentUser | null;
  loading: boolean;
  login: (input: LoginInput) => Promise<CurrentUser>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  hasRole: (...roles: Role[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      try {
        return await api<CurrentUser>("/auth/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 60_000,
  });
  const refresh = async () => {
    await me.refetch();
  };
  const login = async (input: LoginInput) => {
    await post("/auth/login", input);
    const user = await api<CurrentUser>("/auth/me");
    queryClient.setQueryData(["auth", "me"], user);
    return user;
  };
  const register = async (input: RegisterInput) => {
    await post("/auth/register", input);
  };
  const logout = async () => {
    await post("/auth/logout");
    queryClient.clear();
    queryClient.setQueryData(["auth", "me"], null);
  };
  const user = me.data ?? null;
  return (
    <AuthContext.Provider
      value={{
        user,
        loading: me.isLoading,
        login,
        register,
        logout,
        refresh,
        hasRole: (...allowed) => Boolean(user?.roles.some((role) => allowed.includes(role))),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
