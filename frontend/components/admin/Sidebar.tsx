import styles from "./admin.module.css";
import { AdminIcon, AdminIconName } from "./AdminIcon";

export type AdminMenuKey = "dashboard" | "data-sources" | "faq" | "categories" | "chat-history" | "usage";

type MenuItem = { key: AdminMenuKey; label: string; icon: AdminIconName; href: string };

const menuItems: MenuItem[] = [
  { key: "dashboard", label: "ダッシュボード", icon: "dashboard", href: "/" },
  { key: "data-sources", label: "データソース管理", icon: "database", href: "/data-sources" },
  { key: "faq", label: "ＦＡＱ管理", icon: "help", href: "/faqs" },
  { key: "categories", label: "カテゴリ設定", icon: "list", href: "/categories" },
  { key: "chat-history", label: "チャット履歴", icon: "chat", href: "/chat-history" },
  { key: "usage", label: "利用状況管理", icon: "chart", href: "/usage" },
];

type SidebarProps = {
  activeMenu: AdminMenuKey;
  onNavigate: (href: string) => void;
  showMenuTrigger?: boolean;
  collapsed?: boolean;
  onToggle?: () => void;
};

export function Sidebar({ activeMenu, onNavigate, showMenuTrigger = false, collapsed = false, onToggle }: SidebarProps) {
  return (
    <aside className={`${styles.sidebar} ${showMenuTrigger ? styles.sidebarWithMenuTrigger : ""}`} aria-label="管理サイドバー">
      {showMenuTrigger && <button type="button" className={styles.sidebarMenuTrigger} aria-label={collapsed ? "サイドメニューを開く" : "サイドメニューを閉じる"} aria-expanded={!collapsed} onClick={onToggle}>
        <AdminIcon name="menu" size={34} />
      </button>}
      <nav aria-label="管理メニュー">
        {menuItems.map((item) => (
          <button
            key={item.key}
            type="button"
            className={item.key === activeMenu ? styles.activeMenu : undefined}
            aria-current={item.key === activeMenu ? "page" : undefined}
            aria-label={collapsed ? item.label : undefined}
            title={collapsed ? item.label : undefined}
            onClick={() => onNavigate(item.href)}
          >
            <span className={styles.sidebarIcon}><AdminIcon name={item.icon} size={30} /></span>
            <span className={styles.sidebarLabel}>{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
