"use client";

import { ReactNode } from "react";
import { useState } from "react";
import { AdminMenuKey, Sidebar } from "./Sidebar";
import { Header } from "./Header";
import styles from "./admin.module.css";
import { useAuth } from "@/components/auth/AuthProvider";

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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const collapsible = chromeVariant === "sidebar-menu";

  return (
    <div className={`${styles.adminShell} ${collapsible && sidebarCollapsed ? styles.sidebarCollapsed : ""}`}>
      <Header
        userName={userName ?? auth.user?.display_name ?? auth.user?.subject}
        variant={chromeVariant}
        onChatSite={() => onNavigate("/chat")}
        onLogout={() => { void auth.logout(); }}
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
