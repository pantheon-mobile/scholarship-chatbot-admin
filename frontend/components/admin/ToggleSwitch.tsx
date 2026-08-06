import { ButtonHTMLAttributes } from "react";
import styles from "./admin.module.css";

type ToggleSwitchProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> & {
  checked: boolean;
  checkedLabel: string;
  uncheckedLabel: string;
  onChange: (checked: boolean) => void;
};

export function ToggleSwitch({ checked, checkedLabel, uncheckedLabel, onChange, className = "", disabled, ...props }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={`${styles.toggleSwitch} ${checked ? styles.toggleChecked : ""} ${className}`}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      {...props}
    >
      <span className={styles.toggleTrack}><span className={styles.toggleThumb} /></span>
      <span>{checked ? checkedLabel : uncheckedLabel}</span>
    </button>
  );
}
