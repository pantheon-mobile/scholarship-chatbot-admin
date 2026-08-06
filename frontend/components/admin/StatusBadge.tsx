import styles from "./admin.module.css";

export type StatusTone = "neutral" | "info" | "success" | "danger";

export function StatusBadge({ children, tone = "neutral" }: { children: string; tone?: StatusTone }) {
  return <span className={`${styles.statusBadge} ${styles[`status${tone[0].toUpperCase()}${tone.slice(1)}`]}`}>{children}</span>;
}
