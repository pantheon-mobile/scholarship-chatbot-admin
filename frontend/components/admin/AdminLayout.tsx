"use client";

import { ReactNode, useEffect, useRef, useState } from "react";
import { AdminMenuKey, Sidebar } from "./Sidebar";
import { Header } from "./Header";
import styles from "./admin.module.css";
import { useAuth } from "@/components/auth/AuthProvider";
import { fetchChatConfig, recordAdminAccess } from "@/lib/chatApi";
import { fetchMaintenanceCapabilities, purgeAllData } from "@/lib/maintenanceApi";
import { Modal } from "./Modal";

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
  const [purgeEnabled, setPurgeEnabled] = useState(false);
  const [purgeOpen, setPurgeOpen] = useState(false);
  const [purgeConfirmation, setPurgeConfirmation] = useState("");
  const [purgeBusy, setPurgeBusy] = useState(false);
  const [purgeError, setPurgeError] = useState("");
  const [siteName, setSiteName] = useState("東京理科大学奨学金問合せチャット　管理サイト");
  const [headerIconUrl, setHeaderIconUrl] = useState<string | null>(null);
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

  useEffect(() => {
    if (auth.user?.role !== "admin") return;
    void fetchMaintenanceCapabilities().then((result) => setPurgeEnabled(result.bulk_purge_enabled));
  }, [auth.user?.role]);

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
          void auth.logout().then(() => onNavigate("/development/cpf"));
        }}
        showBulkPurge={purgeEnabled}
        onBulkPurge={() => { setPurgeOpen(true); setPurgeConfirmation(""); setPurgeError(""); }}
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
      <Modal
        open={purgeOpen}
        title="一括消去"
        variant="danger"
        confirmLabel={purgeBusy ? "消去中…" : "一括消去する"}
        busy={purgeBusy}
        confirmDisabled={purgeConfirmation !== "一括消去"}
        error={purgeError}
        onClose={() => { if (!purgeBusy) setPurgeOpen(false); }}
        onConfirm={() => {
          setPurgeBusy(true); setPurgeError("");
          void purgeAllData().then(() => {
            setPurgeOpen(false);
            onNavigate("/");
          }).catch((error: Error) => setPurgeError(error.message)).finally(() => setPurgeBusy(false));
        }}
      >
        <p>データソース、FAQ、チャット履歴、アクセスログ・操作ログを物理削除します。S3の元ファイルと変換成果物も削除し、Knowledge Baseを同期します。この操作は取り消せません。</p>
        <label>
          確認のため「一括消去」と入力してください。
          <input className={styles.purgeConfirmationInput} value={purgeConfirmation} onChange={(event) => setPurgeConfirmation(event.target.value)} disabled={purgeBusy} />
        </label>
      </Modal>
    </div>
  );
}
