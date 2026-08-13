import styles from "./admin.module.css";
import { AdminIcon } from "./AdminIcon";

type HeaderProps = {
  userName?: string;
  siteName?: string;
  variant?: "default" | "sidebar-menu";
};

export function Header({
  userName = "東京太郎",
  siteName = "東京理科大学奨学金問合せチャット　管理サイト",
  variant = "default",
}: HeaderProps) {
  return (
    <header className={styles.topbar}>
      <div className={styles.brand}>
        <span className={styles.schoolIcon}><AdminIcon name="university" size={30} /></span>
        {siteName}
      </div>
      {variant === "sidebar-menu" ? <div className={styles.headerActions}>
        <button type="button" className={styles.chatSiteButton}>チャットサイト</button>
        <button type="button" className={styles.userButton}>{userName}</button>
      </div> : <div className={styles.user}>{userName}<span className={styles.menuIcon}><AdminIcon name="menu" size={30} /></span></div>}
    </header>
  );
}
