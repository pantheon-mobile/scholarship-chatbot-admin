import { TextareaHTMLAttributes } from "react";
import styles from "./admin.module.css";

type CharacterCountTextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  error?: string;
  wrapperClassName?: string;
  textareaClassName?: string;
  maxLength: number;
};

export function CharacterCountTextarea({
  label, error, wrapperClassName = "", textareaClassName = "", value = "", maxLength, id, ...props
}: CharacterCountTextareaProps) {
  const count = String(value).length;
  return <label className={`${styles.textareaField} ${wrapperClassName}`} htmlFor={id}>
    {label && <span className={styles.fieldLabel}>{label}</span>}
    <textarea id={id} className={`${styles.textarea} ${textareaClassName}`} value={value} aria-invalid={Boolean(error)} {...props} />
    <span className={`${styles.characterCount} ${count > maxLength ? styles.characterCountOver : ""}`}>{count} / {maxLength}</span>
    {error && <span className={styles.fieldError}>{error}</span>}
  </label>;
}
