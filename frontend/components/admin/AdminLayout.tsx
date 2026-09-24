"use client";

import { ReactNode, useEffect, useState } from "react";
import { AdminMenuKey, Sidebar } from "./Sidebar";
import { Header } from "./Header";
import styles from "./admin.module.css";
import { fetchDevelopmentCpfConfig } from "@/lib/authApi";
import { useAuth } from "@/components/auth/AuthProvider";
import { fetchChatConfig } from "@/lib/chatApi";

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
  const [siteName, setSiteName] = useState("東京理科大学奨学金問合せチャット　管理サイト");
  const [headerIconUrl, setHeaderIconUrl] = useState<string | null>(null);
  const collapsible = chromeVariant === "sidebar-menu";


  useEffect(() => {
    if (!auth.user) return;
    void fetchChatConfig().then((config) => {
      setSiteName(config.admin_title);
      setHeaderIconUrl(config.header_icon_url ?? null);
    }).catch(() => undefined);
  }, [auth.user]);

  return (
    <div className={`${styles.adminShell} ${collapsible && sidebarCollapsed ? styles.sidebarCollapsed : ""}`}>
      <Header
        siteName={siteName}
        headerIconUrl={headerIconUrl}
        userName={userName ?? auth.user?.display_name ?? auth.user?.subject}
        userId={auth.user?.subject}
        variant={chromeVariant}
        onChatSite={() => onNavigate("/chat")}
        onLogout={() => {
          void auth.logout().then(async () => {
            const path = await fetchDevelopmentCpfConfig().then(() => "/development/cpf").catch(() => "/");
            onNavigate(path);
          });
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
