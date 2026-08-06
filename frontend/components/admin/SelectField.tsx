import { SelectHTMLAttributes } from "react";
import styles from "./admin.module.css";

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  wrapperClassName?: string;
};

export function SelectField({ label, wrapperClassName = "", className = "", id, children, ...props }: SelectFieldProps) {
  return (
    <label className={`${styles.selectField} ${wrapperClassName}`} htmlFor={id}>
      {label && <span className={styles.fieldLabel}>{label}</span>}
      <select id={id} className={`${styles.select} ${className}`} {...props}>{children}</select>
    </label>
  );
}
