"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AdminIcon, AdminLayout, Breadcrumb, Button, Modal, SelectField, ToggleSwitch,
} from "@/components/admin";
import { CategorySelectField } from "@/components/categories/CategorySelectField";
import { fetchCategories } from "@/lib/categoriesApi";
import { fetchDataSourceTypes } from "@/lib/api";
import { createWebsiteDataSources, downloadWebsiteImportTemplate, importWebsiteDataSources } from "@/lib/dataSourcesApi";
import { validateWebsiteUrl } from "@/lib/websiteUrlValidation";
import { Priority } from "@/types/dataSource";
import { ClassificationType } from "@/types/dataSourceTypes";
import { Category } from "@/types/category";
import styles from "./page.module.css";

type FormValues = {
  url: string;
  category_id: string;
  type_1_value_id: string;
  type_2_value_id: string;
  type_3_value_id: string;
  priority: Priority;
  answer_source_enabled: boolean;
  reference_link_visible: boolean;
};

const initialValues: FormValues = {
  url: "", category_id: "", type_1_value_id: "", type_2_value_id: "", type_3_value_id: "",
  priority: "MEDIUM", answer_source_enabled: true, reference_link_visible: true,
};
const leaveMessage = "Webサイトを追加せずにデータソース一覧に戻ります。よろしいですか？";

export default function DataSourceWebsiteNewPage() {
  const router = useRouter();
  const [values, setValues] = useState<FormValues>(initialValues);
  const [types, setTypes] = useState<ClassificationType[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const dirty = Boolean(importFile) || (Object.keys(values) as Array<keyof FormValues>).some((key) => values[key] !== initialValues[key]);

  useEffect(() => {
    fetchDataSourceTypes().then(setTypes).catch(() => setError("種別の取得に失敗しました。"));
    fetchCategories().then((result) => setCategories(result.items)).catch(() => setError("カテゴリの取得に失敗しました。"));
  }, []);
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  const typeMap = useMemo(() => Object.fromEntries(types.map((type) => [type.type_code, type])), [types]);
  const setValue = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
    setError(null);
  };
  const requestNavigate = (path: string) => {
    if (busy) return;
    if (dirty) setLeaveOpen(true);
    else router.push(path);
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    const lines = values.url.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (!importFile && lines.length === 0) return;
    if (lines.length > 100) return setError("一度に登録できるURLは100件までです。");
    const items = lines.map((line) => {
      const separator = line.indexOf(",");
      return {
        url: (separator < 0 ? line : line.slice(0, separator)).trim(),
        title: (separator < 0 ? "" : line.slice(separator + 1)).trim(),
      };
    });
    for (const [index, item] of items.entries()) {
      const validationError = validateWebsiteUrl(item.url);
      if (validationError) return setError(`${index + 1}行目: ${validationError}`);
      if (item.title.length > 500) return setError(`${index + 1}行目: タイトルは500文字以内で入力してください。`);
    }
    setBusy(true);
    try {
      const settings = {
        category_id: values.category_id ? Number(values.category_id) : null,
        type_1_value_id: values.type_1_value_id ? Number(values.type_1_value_id) : null,
        type_2_value_id: values.type_2_value_id ? Number(values.type_2_value_id) : null,
        type_3_value_id: values.type_3_value_id ? Number(values.type_3_value_id) : null,
        priority: values.priority,
        answer_source_enabled: values.answer_source_enabled,
        reference_link_visible: values.reference_link_visible,
      };
      if (importFile) await importWebsiteDataSources(importFile, settings);
      else await createWebsiteDataSources(items.map((item) => ({ ...item, ...settings })));
      setValues(initialValues);
      setImportFile(null);
      router.push("/data-sources");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Webサイトの追加に失敗しました。");
    } finally {
      setBusy(false);
    }
  };
  const downloadTemplate = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const blob = await downloadWebsiteImportTemplate();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "urllistformat.xlsx";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "URLリストフォーマットのダウンロードに失敗しました。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AdminLayout activeMenu="data-sources" contentWidth="wide" contentAlign="start" onNavigate={requestNavigate}>
      <form className={styles.page} onSubmit={submit}>
        <div className={styles.topRow}>
          <Breadcrumb items={[{ label: "データソース一覧", onClick: () => requestNavigate("/data-sources") }, { label: "Webサイト追加" }]} />
          <div className={styles.topActions}>
            <Button variant="download" icon={<AdminIcon name="download" size={18} />} onClick={() => void downloadTemplate()} disabled={busy}>フォーマットをダウンロード</Button>
            <Button variant="secondary" icon={<AdminIcon name="back" size={19} />} onClick={() => requestNavigate("/data-sources")} disabled={busy}>データソース一覧に戻る</Button>
          </div>
        </div>
        <div className={styles.divider} />
        {error && <div className={styles.error} role="alert">{error}</div>}
        <div className={styles.formRows}>
          <div className={`${styles.formRow} ${styles.urlRow}`}>
            <span className={styles.rowLabel}>WebサイトURL（必須）：</span>
            <div className={styles.urlInputArea}>
              <textarea className={styles.urlTextarea} aria-label="WebサイトURL" value={values.url} maxLength={100000} disabled={busy || Boolean(importFile)} placeholder="https://www.example.com/" onChange={(event) => setValue("url", event.target.value)} />
              <div className={styles.urlHelp}>※複数のURLは改行して入力してください。タイトルを指定する場合は「URL,タイトル」の形式で入力してください。<br/>※タイトル未指定時は、クロール後にWebサイトのtitleタグを登録します。取得できない場合はURLを使用します。</div>
            </div>
            <div className={styles.importControls}>
              <Button variant="secondary" icon={<AdminIcon name="upload" size={18} />} onClick={() => importInputRef.current?.click()} disabled={busy}>ファイルから一括入力</Button>
              {importFile && <><span className={styles.importFileName}>{importFile.name}</span><Button variant="text" onClick={() => setImportFile(null)} disabled={busy}>選択解除</Button></>}
              <input ref={importInputRef} className={styles.hiddenFileInput} type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" aria-label="URLリスト取込ファイル" onChange={(event) => { const file = event.target.files?.[0] ?? null; setImportFile(file); if (file) setValue("url", ""); event.currentTarget.value = ""; }} />
            </div>
          </div>
          <div className={styles.formRow}>
            <span className={styles.rowLabel}>カテゴリ：</span>
            <CategorySelectField wrapperClassName={styles.categoryField} aria-label="カテゴリ" categories={categories} value={values.category_id} disabled={busy} onChange={(event) => setValue("category_id", event.target.value)} />
          </div>
          <div className={`${styles.formRow} ${styles.classificationRow}`}>
            <span className={styles.rowLabel}>種別：</span>
            <div className={styles.classificationFields}>{(["TYPE_1", "TYPE_2", "TYPE_3"] as const).map((code, index) => {
              const key = `type_${index + 1}_value_id` as "type_1_value_id" | "type_2_value_id" | "type_3_value_id";
              const type = typeMap[code];
              return <div className={styles.classificationField} key={code}><span>{type?.display_label ?? `種別${index + 1}`}</span><SelectField aria-label={type?.display_label ?? `種別${index + 1}`} value={values[key]} disabled={busy} onChange={(event) => setValue(key, event.target.value)}><option value="">未選択</option>{type?.values.map((value) => <option key={value.id} value={value.id}>{value.value_name}</option>)}</SelectField></div>;
            })}</div>
          </div>
          <div className={styles.formRow}>
            <span className={styles.rowLabel}>回答利用の優先度：</span>
            <SelectField wrapperClassName={styles.priorityField} aria-label="回答利用の優先度" value={values.priority} disabled={busy} onChange={(event) => setValue("priority", event.target.value as Priority)}><option value="HIGH">優先度高</option><option value="MEDIUM">優先度中</option><option value="LOW">優先度低</option></SelectField>
          </div>
          <div className={`${styles.formRow} ${styles.toggleRow}`}>
            <span className={styles.rowLabel}>チャットの回答ソースとして利用：</span>
            <ToggleSwitch checked={values.answer_source_enabled} checkedLabel="有効" uncheckedLabel="無効" disabled={busy} onChange={(value) => setValue("answer_source_enabled", value)} />
          </div>
          <div className={`${styles.formRow} ${styles.toggleRow}`}>
            <span className={styles.rowLabel}>チャットの回答に参照元リンクとして表示：</span>
            <ToggleSwitch checked={values.reference_link_visible} checkedLabel="表示" uncheckedLabel="非表示" disabled={busy} onChange={(value) => setValue("reference_link_visible", value)} />
          </div>
        </div>
        <div className={styles.actions}>
          <Button type="submit" variant="primary" disabled={(!values.url.trim() && !importFile) || busy}>{busy ? "追加中..." : "Webサイトを追加する"}</Button>
          <Button variant="secondary" onClick={() => requestNavigate("/data-sources")} disabled={busy}>キャンセル</Button>
        </div>
      </form>
      <Modal open={leaveOpen} title="確認" confirmLabel="一覧に戻る" busy={busy} closeOnBackdrop={!busy} closeOnEscape={!busy} onClose={() => { if (!busy) setLeaveOpen(false); }} onConfirm={() => {
        if (busy) return;
        setLeaveOpen(false);
        setValues(initialValues);
        setImportFile(null);
        router.push("/data-sources");
      }}>{leaveMessage}</Modal>
    </AdminLayout>
  );
}
