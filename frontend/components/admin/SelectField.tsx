import { SelectHTMLAttributes } from "react";
import styles from "./admin.module.css";

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  error?: string;
  wrapperClassName?: string;
};

export function SelectField({ label, error, wrapperClassName = "", className = "", id, children, ...props }: SelectFieldProps) {
  return (
    <label className={`${styles.selectField} ${wrapperClassName}`} htmlFor={id}>
      {label && <span className={styles.fieldLabel}>{label}</span>}
      <select id={id} className={`${styles.select} ${className}`} aria-invalid={Boolean(error)} {...props}>{children}</select>
      {error && <span className={styles.fieldError}>{error}</span>}
    </label>
  );
}
