import { ReactNode } from "react";
import styles from "./admin.module.css";

type PageHeaderProps = { title: string; actions?: ReactNode };

export function PageHeader({ title, actions }: PageHeaderProps) {
  return (
    <div className={styles.pageHeader}>
      <h1>{title}</h1>
      {actions && <div className={styles.pageActions}>{actions}</div>}
    </div>
  );
}
