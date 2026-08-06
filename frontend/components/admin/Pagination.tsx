import { FormEvent, useEffect, useState } from "react";
import { Button } from "./Button";
import styles from "./admin.module.css";

type PaginationProps = {
  page: number;
  totalPages: number;
  disabled?: boolean;
  onPageChange: (page: number) => void;
  onInvalidPage?: (page: number) => void;
};

export function Pagination({ page, totalPages, disabled = false, onPageChange, onInvalidPage }: PaginationProps) {
  const [input, setInput] = useState(String(page));
  useEffect(() => setInput(String(page)), [page]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const next = Number(input);
    if (!Number.isInteger(next) || next < 1 || next > totalPages) {
      onInvalidPage?.(next);
      setInput(String(page));
      return;
    }
    onPageChange(next);
  };
  const last = Math.max(totalPages, 1);

  return (
    <nav className={styles.pagination} aria-label="ページング">
      <Button variant="secondary" className={styles.pageButton} onClick={() => onPageChange(1)} disabled={disabled || page <= 1}>先頭</Button>
      <Button variant="secondary" className={styles.pageButton} onClick={() => onPageChange(page - 1)} disabled={disabled || page <= 1}>前へ</Button>
      <span>{totalPages}ページ中</span>
      <form onSubmit={submit} className={styles.pageInputForm}>
        <input aria-label="ページ番号" type="number" min="1" value={input} onChange={(event) => setInput(event.target.value)} disabled={disabled} />
        <span>ページ目</span>
      </form>
      <Button variant="secondary" className={styles.pageButton} onClick={() => onPageChange(page + 1)} disabled={disabled || page >= last}>次へ</Button>
      <Button variant="secondary" className={styles.pageButton} onClick={() => onPageChange(last)} disabled={disabled || page >= last}>最後</Button>
    </nav>
  );
}
