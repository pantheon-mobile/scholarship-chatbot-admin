import { AdminIcon } from "./AdminIcon";
import styles from "./admin.module.css";

type FileSelectionListProps = {
  files: File[];
  disabled?: boolean;
  formatSize: (size: number) => string;
  onRemove: (index: number) => void;
};

export function FileSelectionList({ files, disabled = false, formatSize, onRemove }: FileSelectionListProps) {
  return (
    <section className={styles.fileSelection} aria-live="polite">
      <h2>選択中のファイル（サイズ）：{files.length}件</h2>
      {files.length > 0 && <ul>{files.map((file, index) => <li key={`${file.name}-${file.size}-${index}`}>
        <span>・{file.name}（{formatSize(file.size)}）</span>
        <button type="button" aria-label={`${file.name}を選択から外す`} onClick={() => onRemove(index)} disabled={disabled}>
          <AdminIcon name="close" size={17} />
        </button>
      </li>)}</ul>}
    </section>
  );
}
