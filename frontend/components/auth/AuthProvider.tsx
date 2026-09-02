"use client";

import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { fetchAuthenticatedUser, logout as requestLogout } from "@/lib/authApi";
import { AuthenticatedUser } from "@/types/auth";
import styles from "./auth.module.css";
import { canAccessAdminPath } from "@/lib/permissions";

type AuthContextValue = {
  user: AuthenticatedUser | null;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue>({
  user: null,
  logout: async () => undefined,
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isSsoReceiver = pathname === "/sso/cpf" || pathname === "/development/cpf";
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [checking, setChecking] = useState(!isSsoReceiver);
  const [unauthorized, setUnauthorized] = useState(false);

  useEffect(() => {
    if (isSsoReceiver) {
      setChecking(false);
      return;
    }
    setChecking(true);
    fetchAuthenticatedUser()
      .then((current) => {
        setUser(current);
        setUnauthorized(false);
      })
      .catch(() => {
        setUser(null);
        setUnauthorized(true);
      })
      .finally(() => setChecking(false));
  }, [isSsoReceiver]);

  const value = useMemo(() => ({
    user,
    logout: async () => {
      await requestLogout();
      setUser(null);
      setUnauthorized(true);
    },
  }), [user]);

  if (isSsoReceiver) return <>{children}</>;
  if (checking) return <main className={styles.state}><div className={styles.spinner} /><p>ログイン情報を確認しています。</p></main>;
  if (unauthorized || !user) return <main className={styles.state}><section className={styles.card}><h1>認証が必要です</h1><p>CPFのメニューから管理画面へ入り直してください。</p></section></main>;
  if (!canAccessAdminPath(user.role, pathname)) return <main className={styles.state}><section className={styles.card}><h1>アクセス権限がありません</h1><p>この機能はシステム管理者のみ利用できます。</p></section></main>;
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
