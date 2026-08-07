import { ReactNode } from "react";
import styles from "./admin.module.css";

export type BreadcrumbItem = { label: ReactNode; onClick?: () => void };

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className={styles.breadcrumb} aria-label="パンくず">
      <ol>{items.map((item, index) => <li key={index}>
        {item.onClick ? <button type="button" onClick={item.onClick}>{item.label}</button> : <span aria-current="page">{item.label}</span>}
      </li>)}</ol>
    </nav>
  );
}
