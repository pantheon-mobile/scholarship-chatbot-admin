import { InputHTMLAttributes, ReactNode } from "react";
import styles from "./admin.module.css";

type FormFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  description?: ReactNode;
  error?: string;
  compact?: boolean;
  inputClassName?: string;
  wrapperClassName?: string;
};

export function FormField({ label, description, error, compact = false, inputClassName = "", wrapperClassName = "", id, ...props }: FormFieldProps) {
  return (
    <label className={`${styles.formField} ${compact ? styles.compactField : ""} ${wrapperClassName}`} htmlFor={id}>
      {label && <span className={styles.fieldLabel}>{label}</span>}
      <input id={id} className={`${styles.input} ${inputClassName}`} aria-invalid={Boolean(error)} {...props} />
      {description && <span className={styles.fieldDescription}>{description}</span>}
      {error && <span className={styles.fieldError}>{error}</span>}
    </label>
  );
}
