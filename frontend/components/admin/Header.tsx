import styles from "./admin.module.css";
import { AdminIcon } from "./AdminIcon";

type HeaderProps = {
  userName?: string;
  siteName?: string;
  variant?: "default" | "sidebar-menu";
  onChatSite?: () => void;
  onLogout?: () => void;
};

export function Header({
  userName = "東京太郎",
  siteName = "東京理科大学奨学金問合せチャット　管理サイト",
  variant = "default",
  onChatSite,
  onLogout,
}: HeaderProps) {
  return (
    <header className={styles.topbar}>
      <div className={styles.brand}>
        <span className={styles.schoolIcon}><AdminIcon name="university" size={30} /></span>
        {siteName}
      </div>
      {variant === "sidebar-menu" ? <div className={styles.headerActions}>
        <button type="button" className={styles.chatSiteButton} onClick={onChatSite}>チャットサイト</button>
        <span className={styles.userName}>{userName}</span>
        <button type="button" className={styles.userButton} onClick={onLogout}>ログアウト</button>
      </div> : <div className={styles.user}>{userName}<span className={styles.menuIcon}><AdminIcon name="menu" size={30} /></span></div>}
    </header>
  );
}
