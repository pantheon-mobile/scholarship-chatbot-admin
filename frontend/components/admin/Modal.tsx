"use client";

import { ReactNode, useEffect, useId, useRef } from "react";
import { Button, ButtonVariant } from "./Button";
import styles from "./admin.module.css";

type ModalVariant = "default" | "danger";

type ModalProps = {
  open: boolean;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  error?: ReactNode;
  variant?: ModalVariant;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: ButtonVariant;
  busy?: boolean;
  confirmDisabled?: boolean;
  closeOnBackdrop?: boolean;
  closeOnEscape?: boolean;
  onConfirm?: () => void;
  onClose: () => void;
};

const focusableSelector = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export function Modal({
  open,
  title,
  children,
  footer,
  error,
  variant = "default",
  confirmLabel = "OK",
  cancelLabel = "キャンセル",
  confirmVariant,
  busy = false,
  confirmDisabled = false,
  closeOnBackdrop = true,
  closeOnEscape = true,
  onConfirm,
  onClose,
}: ModalProps) {
  const titleId = useId();
  const bodyId = useId();
  const dialogRef = useRef<HTMLElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const stateRef = useRef({ busy, closeOnEscape, onClose, variant });
  stateRef.current = { busy, closeOnEscape, onClose, variant };

  useEffect(() => {
    if (!open) return;

    previouslyFocusedRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusTimer = window.setTimeout(() => {
      const firstFocusable = dialogRef.current?.querySelector<HTMLElement>(focusableSelector);
      (cancelRef.current ?? firstFocusable ?? dialogRef.current)?.focus();
    }, 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!stateRef.current.busy && stateRef.current.closeOnEscape) stateRef.current.onClose();
        return;
      }

      if (event.key === "Enter" && stateRef.current.variant === "danger") {
        event.preventDefault();
        return;
      }

      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(focusableSelector));
      if (focusable.length === 0) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocusedRef.current?.focus();
    };
  }, [open]);

  if (!open) return null;

  const resolvedConfirmVariant = confirmVariant ?? (variant === "danger" ? "danger" : "primary");
  const defaultFooter = onConfirm ? (
    <>
      <Button ref={cancelRef} className={styles.modalButton} variant="secondary" onClick={onClose} disabled={busy}>
        {cancelLabel}
      </Button>
      <Button className={styles.modalButton} variant={resolvedConfirmVariant} onClick={onConfirm} disabled={busy || confirmDisabled}>
        {confirmLabel}
      </Button>
    </>
  ) : (
    <Button ref={cancelRef} className={styles.modalButton} variant="secondary" onClick={onClose} disabled={busy}>
      {cancelLabel}
    </Button>
  );

  return (
    <div
      className={styles.modalBackdrop}
      role="presentation"
      onMouseDown={() => {
        if (!busy && closeOnBackdrop) onClose();
      }}
    >
      <section
        ref={dialogRef}
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        aria-busy={busy}
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className={styles.modalHeader}>
          <h2 id={titleId}>{title}</h2>
        </header>
        <div id={bodyId} className={styles.modalBody}>
          {children}
          {error && <div className={styles.modalError} role="alert">{error}</div>}
        </div>
        <footer className={styles.modalFooter}>{footer ?? defaultFooter}</footer>
      </section>
    </div>
  );
}
