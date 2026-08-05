import { ButtonHTMLAttributes, forwardRef, ReactNode } from "react";
import styles from "./admin.module.css";

export type ButtonVariant = "primary" | "secondary" | "danger" | "text" | "download" | "add";
export type ButtonFocusTone = "primary" | "neutral" | "danger";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  focusTone?: ButtonFocusTone;
  icon?: ReactNode;
};

const defaultFocusTone: Record<ButtonVariant, ButtonFocusTone> = {
  primary: "primary",
  secondary: "neutral",
  danger: "danger",
  text: "primary",
  download: "primary",
  add: "primary",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", focusTone, icon, className = "", children, type = "button", ...props },
  ref,
) {
  const resolvedFocusTone = focusTone ?? defaultFocusTone[variant];

  return (
    <button
      ref={ref}
      type={type}
      className={`${styles.button} ${styles[variant]} ${styles[`focus${resolvedFocusTone[0].toUpperCase()}${resolvedFocusTone.slice(1)}`]} ${className}`}
      {...props}
    >
      {icon && <span className={styles.buttonIcon} aria-hidden="true">{icon}</span>}
      {children}
    </button>
  );
});
