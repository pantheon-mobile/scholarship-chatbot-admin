import { ReactNode } from "react";
import { AdminMenuKey, Sidebar } from "./Sidebar";
import { Header } from "./Header";
import styles from "./admin.module.css";

type AdminLayoutProps = {
  children: ReactNode;
  activeMenu: AdminMenuKey;
  onNavigate: (href: string) => void;
  userName?: string;
  contentWidth?: "default" | "wide" | "full";
  contentAlign?: "center" | "start";
};

export function AdminLayout({
  children,
  activeMenu,
  onNavigate,
  userName,
  contentWidth = "default",
  contentAlign = "center",
}: AdminLayoutProps) {
  return (
    <div className={styles.adminShell}>
      <Header userName={userName} />
      <Sidebar activeMenu={activeMenu} onNavigate={onNavigate} />
      <main className={styles.adminContent}>
        <div className={`${styles.contentInner} ${styles[`content${contentWidth[0].toUpperCase()}${contentWidth.slice(1)}`]} ${styles[`contentAlign${contentAlign[0].toUpperCase()}${contentAlign.slice(1)}`]}`}>
          {children}
        </div>
      </main>
    </div>
  );
}
