"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AdminIcon, AdminLayout, Breadcrumb, Button, FileDropzone, FileSelectionList,
  FormField, Modal, SelectField, ToggleSwitch,
} from "@/components/admin";
import { CategorySelectField } from "@/components/categories/CategorySelectField";
import { fetchCategories } from "@/lib/categoriesApi";
import { fetchDataSourceTypes } from "@/lib/api";
import { createFileDataSources } from "@/lib/dataSourceFilesApi";
import { FILE_ACCEPT, validateSelectedFiles } from "@/lib/fileUploadValidation";
import { ClassificationType } from "@/types/dataSourceTypes";
import { Category } from "@/types/category";
import styles from "./page.module.css";

const leaveMessage = "ファイルを追加せずにデータソース一覧に戻ります。よろしいですか？";

function formatSize(size: number) {
  if (size < 1024) return `${size}B`;
  if (size < 1024 ** 2) return `${Math.ceil(size / 1024)}KB`;
  return `${(size / 1024 ** 2).toFixed(size >= 10 * 1024 ** 2 ? 1 : 2)}MB`;
}

export default function DataSourceFileNewPage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [types, setTypes] = useState<ClassificationType[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [typeValues, setTypeValues] = useState({ TYPE_1: "", TYPE_2: "", TYPE_3: "" });
  const [priority, setPriority] = useState<"HIGH" | "MEDIUM" | "LOW">("MEDIUM");
  const [answerSource, setAnswerSource] = useState(true);
  const [referenceLink, setReferenceLink] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [validating, setValidating] = useState(false);
  const [leaveTarget, setLeaveTarget] = useState<string | null>(null);

  useEffect(() => {
    fetchDataSourceTypes().then(setTypes).catch(() => setError("種別の取得に失敗しました。"));
    fetchCategories().then((result) => setCategories(result.items)).catch(() => setError("カテゴリの取得に失敗しました。"));
  }, []);
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!files.length) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [files.length]);

  const typeMap = useMemo(() => Object.fromEntries(types.map((type) => [type.type_code, type])), [types]);
  const requestNavigate = (path: string) => {
    if (busy) return;
    if (files.length) setLeaveTarget(path);
    else router.push(path);
  };
  const addFiles = async (incoming: File[]) => {
    if (busy || validating) return;
    setValidating(true);
    try {
      const next = await validateSelectedFiles(files, incoming);
      setFiles(next);
      if (next.length !== 1) setTitle("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "ファイルの追加に失敗しました。");
    } finally {
      setValidating(false);
    }
  };
  const removeFile = (index: number) => {
    if (busy) return;
    setFiles((current) => {
      const next = current.filter((_, itemIndex) => itemIndex !== index);
      if (next.length !== 1) setTitle("");
      return next;
    });
    setError(null);
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!files.length) { setError("ファイルを選択してください。"); return; }
    if (busy || validating) return;
    setBusy(true);
    try {
      await createFileDataSources({
        files, title, category_id: categoryId,
        type_1_value_id: typeValues.TYPE_1,
        type_2_value_id: typeValues.TYPE_2,
        type_3_value_id: typeValues.TYPE_3,
        priority,
        answer_source_enabled: answerSource,
        reference_link_visible: referenceLink,
      });
      setFiles([]);
      router.push("/data-sources");
    } catch (err) {
      setError(err instanceof Error ? err.message : "ファイルの追加に失敗しました。");
      setBusy(false);
    }
  };

  return (
    <AdminLayout activeMenu="data-sources" contentWidth="wide" contentAlign="start" onNavigate={requestNavigate}>
      <form className={styles.page} onSubmit={submit}>
        <div className={styles.topRow}>
          <Breadcrumb items={[{ label: "データソース一覧", onClick: () => requestNavigate("/data-sources") }, { label: "ファイル追加" }]} />
          <Button variant="secondary" icon={<AdminIcon name="back" size={19} />} onClick={() => requestNavigate("/data-sources")} disabled={busy}>データソース一覧に戻る</Button>
        </div>

        <section className={styles.uploadSection}>
          <h1>ファイル（必須）：</h1>
          <FileDropzone accept={FILE_ACCEPT} disabled={busy || validating} onFiles={addFiles} />
          <div className={styles.uploadNotes}>
            <span>※利用可能な形式：.pdf、.doc、.docx、.xls、.xlsx、.ppt、.pptx、.txt、.csv</span>
            <span>※1度に追加できるファイル容量は100MBまでで、最大20件選択できます。</span>
          </div>
        </section>

        <FileSelectionList files={files} disabled={busy} formatSize={formatSize} onRemove={removeFile} />
        {error && <div className={styles.error} role="alert">{error}</div>}

        <div className={styles.divider} />
        <div className={styles.formRows}>
          <div className={styles.formRow}>
            <span className={styles.rowLabel}>タイトル：</span>
            <FormField wrapperClassName={styles.titleField} aria-label="タイトル" value={title} maxLength={500} disabled={busy || files.length !== 1} placeholder="※1ファイルのみ選択している場合に入力できます。" onChange={(event) => setTitle(event.target.value)} description="※未入力の場合、タイトルはファイル名となります。" />
          </div>
          <div className={styles.formRow}>
            <span className={styles.rowLabel}>カテゴリ：</span>
            <div className={styles.categoryField}>
              <CategorySelectField wrapperClassName={styles.mediumField} aria-label="カテゴリ" categories={categories} value={categoryId} disabled={busy} onChange={(event) => setCategoryId(event.target.value)} />
              <p className={styles.categoryNote}>
                ※複数ファイルを選択した場合、全てのファイルに同じカテゴリが適用されます。<br />
                カテゴリをファイルごとに変えたい場合は未設定にして追加後、個別に編集してください。
              </p>
            </div>
          </div>
          <div className={`${styles.formRow} ${styles.classificationRow}`}>
            <span className={styles.rowLabel}>種別：</span>
            <div className={styles.classificationFields}>{(["TYPE_1", "TYPE_2", "TYPE_3"] as const).map((code, index) => {
              const type = typeMap[code];
              return <div className={styles.classificationField} key={code}><span>{type?.display_label ?? `種別${index + 1}`}</span><SelectField aria-label={type?.display_label ?? `種別${index + 1}`} value={typeValues[code]} disabled={busy} onChange={(event) => setTypeValues((current) => ({ ...current, [code]: event.target.value }))}><option value="">{type?.display_label ?? `種別${index + 1}`}を選択</option>{type?.values.map((value) => <option key={value.id} value={value.id}>{value.value_name}</option>)}</SelectField></div>;
            })}</div>
          </div>
          <div className={styles.formRow}>
            <span className={styles.rowLabel}>回答利用の優先度：</span>
            <SelectField wrapperClassName={styles.priorityField} aria-label="回答利用の優先度" value={priority} disabled={busy} onChange={(event) => setPriority(event.target.value as "HIGH" | "MEDIUM" | "LOW")}><option value="HIGH">優先度高</option><option value="MEDIUM">優先度中</option><option value="LOW">優先度低</option></SelectField>
          </div>
          <div className={`${styles.formRow} ${styles.toggleRow}`}>
            <span className={styles.rowLabel}>チャットの回答ソースとして利用：</span>
            <ToggleSwitch checked={answerSource} checkedLabel="有効" uncheckedLabel="無効" disabled={busy} onChange={setAnswerSource} />
          </div>
          <div className={`${styles.formRow} ${styles.toggleRow}`}>
            <span className={styles.rowLabel}>チャットの回答に参照元リンクとして表示：</span>
            <ToggleSwitch checked={referenceLink} checkedLabel="表示" uncheckedLabel="非表示" disabled={busy} onChange={setReferenceLink} />
          </div>
        </div>

        <div className={styles.actions}>
          <Button type="submit" variant="primary" disabled={!files.length || busy || validating}>{busy ? "ファイルを追加中..." : validating ? "ファイルを確認中..." : "ファイルを追加する"}</Button>
          <Button variant="secondary" onClick={() => requestNavigate("/data-sources")} disabled={busy}>キャンセル</Button>
        </div>
      </form>

      <Modal open={Boolean(leaveTarget)} title="確認" confirmLabel="一覧に戻る" busy={busy} closeOnBackdrop={!busy} closeOnEscape={!busy} onClose={() => { if (!busy) setLeaveTarget(null); }} onConfirm={() => {
        if (!leaveTarget || busy) return;
        const target = leaveTarget;
        setLeaveTarget(null);
        setFiles([]);
        router.push(target);
      }}>{leaveMessage}</Modal>
    </AdminLayout>
  );
}
