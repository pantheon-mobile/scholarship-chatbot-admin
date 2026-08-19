"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AdminIcon, AdminLayout, Breadcrumb, Button, FormField, Modal, SelectField, ToggleSwitch,
} from "@/components/admin";
import { CategorySelectField } from "@/components/categories/CategorySelectField";
import { fetchCategories } from "@/lib/categoriesApi";
import { fetchDataSourceTypes } from "@/lib/api";
import { fetchDataSource, updateFileDataSource } from "@/lib/dataSourcesApi";
import { DataSource, DataSourcesApiError, Priority } from "@/types/dataSource";
import { ClassificationType } from "@/types/dataSourceTypes";
import { Category } from "@/types/category";
import styles from "./page.module.css";

type EditableValues = {
  title: string;
  category_id: string;
  type_1_value_id: string;
  type_2_value_id: string;
  type_3_value_id: string;
  priority: Priority;
  answer_source_enabled: boolean;
  reference_link_visible: boolean;
};

const emptyValues: EditableValues = {
  title: "",
  category_id: "",
  type_1_value_id: "",
  type_2_value_id: "",
  type_3_value_id: "",
  priority: "MEDIUM",
  answer_source_enabled: true,
  reference_link_visible: true,
};

const leaveMessage = "情報を更新せずにデータソース一覧に戻ります。よろしいですか？";

function valuesFrom(row: DataSource): EditableValues {
  const selected = Object.fromEntries(row.classifications.map((item) => [item.type_code, String(item.classification_value_id)]));
  return {
    title: row.title,
    category_id: row.category ? String(row.category.id) : "",
    type_1_value_id: selected.TYPE_1 ?? "",
    type_2_value_id: selected.TYPE_2 ?? "",
    type_3_value_id: selected.TYPE_3 ?? "",
    priority: row.priority,
    answer_source_enabled: row.answer_source_enabled,
    reference_link_visible: row.reference_link_visible,
  };
}

function formatSize(size: number | null) {
  if (size === null) return "－";
  if (size < 1024) return `${size}B`;
  if (size < 1024 ** 2) return `${Math.ceil(size / 1024)}KB`;
  return `${(size / 1024 ** 2).toFixed(size >= 10 * 1024 ** 2 ? 1 : 2)}MB`;
}

export default function DataSourceFileEditPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const dataSourceId = Number(params.id);
  const [row, setRow] = useState<DataSource | null>(null);
  const [types, setTypes] = useState<ClassificationType[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [initial, setInitial] = useState<EditableValues | null>(null);
  const [values, setValues] = useState<EditableValues>(emptyValues);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leaveOpen, setLeaveOpen] = useState(false);

  useEffect(() => {
    if (!Number.isInteger(dataSourceId) || dataSourceId < 1) {
      setError("指定されたデータソースが見つかりません。");
      setLoading(false);
      return;
    }
    fetchCategories().then((result) => setCategories(result.items)).catch(() => setError("カテゴリの取得に失敗しました。"));
    Promise.all([fetchDataSource(dataSourceId), fetchDataSourceTypes()])
      .then(([data, classificationTypes]) => {
        if (data.source_type !== "FILE" || !data.file) {
          setError("ファイル編集の対象ではありません。");
          return;
        }
        const editable = valuesFrom(data);
        setRow(data);
        setTypes(classificationTypes);
        setInitial(editable);
        setValues(editable);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "データソース情報の取得に失敗しました。"))
      .finally(() => setLoading(false));
  }, [dataSourceId]);

  const dirty = initial !== null && (Object.keys(values) as Array<keyof EditableValues>).some((key) => values[key] !== initial[key]);
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
  const requestNavigate = (path: string) => {
    if (busy) return;
    if (dirty) setLeaveOpen(true);
    else router.push(path);
  };
  const setValue = <K extends keyof EditableValues>(key: K, value: EditableValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
    setError(null);
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!row || !dirty || busy) return;
    setBusy(true);
    try {
      const updated = await updateFileDataSource(row.id, {
        title: values.title,
        category_id: values.category_id ? Number(values.category_id) : null,
        type_1_value_id: values.type_1_value_id ? Number(values.type_1_value_id) : null,
        type_2_value_id: values.type_2_value_id ? Number(values.type_2_value_id) : null,
        type_3_value_id: values.type_3_value_id ? Number(values.type_3_value_id) : null,
        priority: values.priority,
        answer_source_enabled: values.answer_source_enabled,
        reference_link_visible: values.reference_link_visible,
        version: row.version,
      });
      setRow(updated);
      const editable = valuesFrom(updated);
      setInitial(editable);
      setValues(editable);
      router.push("/data-sources");
    } catch (err) {
      if (err instanceof DataSourcesApiError && err.code === "VERSION_CONFLICT") {
        setError("他の操作で情報が更新されています。再読み込みしてください。");
      } else {
        setError(err instanceof Error ? err.message : "データソースの更新に失敗しました。");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <AdminLayout activeMenu="data-sources" contentWidth="wide" contentAlign="start" onNavigate={requestNavigate}>
      <form className={styles.page} onSubmit={submit}>
        <div className={styles.topRow}>
          <Breadcrumb items={[
            { label: "データソース一覧", onClick: () => requestNavigate("/data-sources") },
            { label: "データソース情報編集（ファイル）" },
          ]} />
          <Button variant="secondary" icon={<AdminIcon name="back" size={19} />} onClick={() => requestNavigate("/data-sources")} disabled={busy}>
            データソース一覧に戻る
          </Button>
        </div>

        {loading ? <div className={styles.loading}>読み込み中...</div> : error && !row ? <div className={styles.error} role="alert">{error}</div> : row && <>
          <div className={styles.divider} />
          {error && <div className={styles.error} role="alert">{error}</div>}
          <div className={styles.formRows}>
            <div className={styles.formRow}>
              <span className={styles.rowLabel}>タイトル：</span>
              <FormField wrapperClassName={styles.titleField} aria-label="タイトル" value={values.title} maxLength={500} disabled={busy} onChange={(event) => setValue("title", event.target.value)} description="※未入力の場合、タイトルはファイル名となります。" />
            </div>
            <div className={`${styles.formRow} ${styles.readonlyRow}`}>
              <span className={styles.rowLabel}>ファイル名（サイズ）：</span>
              <span>{row.file?.file_name}（{formatSize(row.size_bytes)}）</span>
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
                return <div className={styles.classificationField} key={code}>
                  <span>{type?.display_label ?? `種別${index + 1}`}</span>
                  <SelectField aria-label={type?.display_label ?? `種別${index + 1}`} value={values[key]} disabled={busy} onChange={(event) => setValue(key, event.target.value)}>
                    <option value="">未選択</option>
                    {type?.values.map((value) => <option key={value.id} value={value.id}>{value.value_name}</option>)}
                  </SelectField>
                </div>;
              })}</div>
            </div>
            <div className={styles.formRow}>
              <span className={styles.rowLabel}>回答利用の優先度：</span>
              <SelectField wrapperClassName={styles.priorityField} aria-label="回答利用の優先度" value={values.priority} disabled={busy} onChange={(event) => setValue("priority", event.target.value as Priority)}>
                <option value="HIGH">優先度高</option><option value="MEDIUM">優先度中</option><option value="LOW">優先度低</option>
              </SelectField>
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
            <Button type="submit" variant="primary" disabled={!dirty || busy}>{busy ? "更新中..." : "更新する"}</Button>
            <Button variant="secondary" onClick={() => requestNavigate("/data-sources")} disabled={busy}>キャンセル</Button>
          </div>
        </>}
      </form>

      <Modal open={leaveOpen} title="確認" confirmLabel="一覧に戻る" busy={busy} closeOnBackdrop={!busy} closeOnEscape={!busy} onClose={() => { if (!busy) setLeaveOpen(false); }} onConfirm={() => {
        if (busy) return;
        setLeaveOpen(false);
        router.push("/data-sources");
      }}>{leaveMessage}</Modal>
    </AdminLayout>
  );
}
