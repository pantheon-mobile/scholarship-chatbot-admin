import { forwardRef, HTMLAttributes, ReactNode, TableHTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";
import styles from "./admin.module.css";

export function TableFrame({ children, className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`${styles.tableFrame} ${className}`} {...props}>{children}</div>;
}

export function Table({ children, className = "", ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={`${styles.table} ${className}`} {...props}>{children}</table>;
}

export const TableRow = forwardRef<HTMLTableRowElement, HTMLAttributes<HTMLTableRowElement>>(function TableRow(
  { children, className = "", ...props },
  ref,
) {
  return <tr ref={ref} className={`${styles.tableRow} ${className}`} {...props}>{children}</tr>;
});

export function TableHeaderCell({ children, className = "", ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={`${styles.tableHeaderCell} ${className}`} {...props}>{children}</th>;
}

export function TableCell({ children, className = "", ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={`${styles.tableCell} ${className}`} {...props}>{children}</td>;
}

export function TableActions({ children }: { children: ReactNode }) {
  return <div className={styles.tableActions}>{children}</div>;
}
