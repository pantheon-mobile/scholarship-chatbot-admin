"use client";

import { ReactNode, useEffect, useRef, useState } from "react";
import { AdminMenuKey, Sidebar } from "./Sidebar";
import { Header } from "./Header";
import styles from "./admin.module.css";
import { useAuth } from "@/components/auth/AuthProvider";
import { recordAdminAccess } from "@/lib/chatApi";

type AdminLayoutProps = {
  children: ReactNode;
  activeMenu: AdminMenuKey;
  onNavigate: (href: string) => void;
  userName?: string;
  contentWidth?: "default" | "wide" | "full";
  contentAlign?: "center" | "start";
  chromeVariant?: "default" | "sidebar-menu";
};

export function AdminLayout({
  children,
  activeMenu,
  onNavigate,
  userName,
  contentWidth = "default",
  contentAlign = "center",
  chromeVariant = "sidebar-menu",
}: AdminLayoutProps) {
  const auth = useAuth();
  const recordedIdentifier = useRef<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const collapsible = chromeVariant === "sidebar-menu";

  useEffect(() => {
    if (!auth.user) return;
    const identifier = `${auth.user.site}:${auth.user.subject}`;
    if (recordedIdentifier.current === identifier) return;
    recordedIdentifier.current = identifier;
    void recordAdminAccess(crypto.randomUUID(), identifier, new Date().toISOString()).catch(() => {
      recordedIdentifier.current = null;
    });
  }, [auth.user]);

  return (
    <div className={`${styles.adminShell} ${collapsible && sidebarCollapsed ? styles.sidebarCollapsed : ""}`}>
      <Header
        userName={userName ?? auth.user?.display_name ?? auth.user?.subject}
        userId={auth.user?.subject}
        variant={chromeVariant}
        onChatSite={() => onNavigate("/chat")}
        onLogout={() => {
          void auth.logout().then(() => onNavigate("/development/cpf"));
        }}
      />
      <Sidebar
        activeMenu={activeMenu}
        onNavigate={onNavigate}
        showMenuTrigger={collapsible}
        collapsed={collapsible && sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((current) => !current)}
        role={auth.user?.role ?? "admin"}
      />
      <main className={styles.adminContent}>
        <div className={`${styles.contentInner} ${styles[`content${contentWidth[0].toUpperCase()}${contentWidth.slice(1)}`]} ${styles[`contentAlign${contentAlign[0].toUpperCase()}${contentAlign.slice(1)}`]}`}>
          {children}
        </div>
      </main>
    </div>
  );
}
