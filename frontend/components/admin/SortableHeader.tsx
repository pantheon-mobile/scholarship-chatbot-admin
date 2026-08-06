import { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./admin.module.css";

type SortDirection = "asc" | "desc" | null;
type SortableHeaderProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  direction: SortDirection;
};

export function SortableHeader({ children, direction, className = "", ...props }: SortableHeaderProps) {
  return (
    <button
      type="button"
      className={`${styles.sortableHeader} ${className}`}
      aria-label={`${children}を${direction === "asc" ? "降順" : "昇順"}で並び替え`}
      {...props}
    >
      <span>{children}</span>
      <span className={styles.sortArrows} aria-hidden="true">
        <span className={direction === "asc" ? styles.sortActive : ""}>▲</span>
        <span className={direction === "desc" ? styles.sortActive : ""}>▼</span>
      </span>
    </button>
  );
}
