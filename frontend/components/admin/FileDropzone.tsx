"use client";

import { ChangeEvent, DragEvent, useId, useRef, useState } from "react";
import { AdminIcon } from "./AdminIcon";
import { Button } from "./Button";
import styles from "./admin.module.css";

type FileDropzoneProps = {
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  onFiles: (files: File[]) => void;
};

export function FileDropzone({ accept, multiple = true, disabled = false, onFiles }: FileDropzoneProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const openPicker = () => { if (!disabled) inputRef.current?.click(); };
  const receive = (files: FileList | null) => {
    if (!disabled && files?.length) onFiles(Array.from(files));
    if (inputRef.current) inputRef.current.value = "";
  };
  const onChange = (event: ChangeEvent<HTMLInputElement>) => receive(event.target.files);
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    receive(event.dataTransfer.files);
  };
  return (
    <div
      className={`${styles.fileDropzone} ${dragging ? styles.fileDropzoneDragging : ""} ${disabled ? styles.fileDropzoneDisabled : ""}`}
      role="group"
      aria-label="ファイルのドラッグ＆ドロップまたは選択"
      aria-disabled={disabled}
      onDragEnter={(event) => { event.preventDefault(); if (!disabled) setDragging(true); }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false); }}
      onDrop={onDrop}
    >
      <input ref={inputRef} id={inputId} className={styles.visuallyHidden} type="file" accept={accept} multiple={multiple} disabled={disabled} onChange={onChange} />
      <AdminIcon name="upload" size={36} />
      <p>ファイルをこのエリアにドラッグ＆ドロップまたはファイル選択を押して追加してください。</p>
      <Button variant="secondary" aria-controls={inputId} onClick={openPicker} disabled={disabled}>ファイル選択</Button>
    </div>
  );
}
