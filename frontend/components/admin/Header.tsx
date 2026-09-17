"use client";

import { useState } from "react";
import Image from "next/image";
import styles from "./admin.module.css";
import { AdminIcon } from "./AdminIcon";

type HeaderProps = {
  userName?: string;
  userId?: string;
  siteName?: string;
  headerIconUrl?: string | null;
  variant?: "default" | "sidebar-menu";
  onChatSite?: () => void;
  onLogout?: () => void;
};

export function Header({
  userName = "東京太郎",
  userId,
  siteName = "東京理科大学奨学金問合せチャット　管理サイト",
  headerIconUrl,
  variant = "default",
  onChatSite,
  onLogout,
}: HeaderProps) {
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  return (
    <header className={styles.topbar}>
      <div className={styles.brand}>
        <span className={styles.schoolIcon}>{headerIconUrl ? <Image className={styles.schoolIconImage} src={headerIconUrl} alt="" width={30} height={30} unoptimized /> : <AdminIcon name="university" size={30} />}</span>
        {siteName}
      </div>
      <div className={styles.headerActions}>
        {variant === "sidebar-menu" && <button type="button" className={styles.chatSiteButton} onClick={onChatSite}>チャットサイト</button>}
        <div className={styles.headerUserWrap}>
          <button type="button" className={styles.userMenuButton} aria-haspopup="menu" aria-expanded={userMenuOpen} onClick={() => setUserMenuOpen((current) => !current)}>{userName} ▾</button>
          {userMenuOpen && <div className={styles.headerUserMenu} role="menu">
            <span>ID：{userId || "-"}</span>
            <button type="button" role="menuitem" onClick={() => setUserMenuOpen(false)}>閉じる</button>
            <button type="button" role="menuitem" onClick={onLogout}>ログアウト</button>
          </div>}
        </div>
      </div>
    </header>
  );
}
