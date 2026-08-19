"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AdminIcon, AdminLayout, Button, Checkbox, FormField, Modal, PageHeader, Pagination,
  SelectField, SortableHeader, StatusBadge, Table, TableCell, TableFrame, TableHeaderCell,
  TableRow, ToggleSwitch,
} from "@/components/admin";
import { CategorySelectField } from "@/components/categories/CategorySelectField";
import { fetchCategories } from "@/lib/categoriesApi";
import { fetchDataSourceTypes } from "@/lib/api";
import {
  bulkDeleteDataSources, deleteDataSource, exportDataSources, fetchDataSources,
  updateAnswerSource, updateReferenceLink,
} from "@/lib/dataSourcesApi";
import { ClassificationType } from "@/types/dataSourceTypes";
import { Category } from "@/types/category";
import { DataSource, DataSourceFilters, DataSourceListResponse, DataSourcesApiError, SortColumn } from "@/types/dataSource";
import styles from "./page.module.css";

const emptyFilters: DataSourceFilters = {
  keyword: "", format: "", status: "", category_id: "", type_1_value_id: "", type_2_value_id: "", type_3_value_id: "",
  answer_source_enabled: "", priority: "", reference_link_visible: "",
  sort: "updated_at", order: "desc", page: 1, page_size: 10,
};
const statusLabels = { PREPARING: "準備中", TRAINING: "学習中", AVAILABLE: "利用可", ERROR: "エラー" } as const;
const statusTones = { PREPARING: "neutral", TRAINING: "info", AVAILABLE: "success", ERROR: "danger" } as const;
const priorityLabels = { HIGH: "高", MEDIUM: "中", LOW: "低" } as const;

function formatBytes(value: number | null) {
  if (value === null) return "－";
  if (value < 1024) return `${value}B`;
  if (value < 1024 ** 2) return `${Math.round(value / 1024)}KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)}MB`;
  return `${(value / 1024 ** 3).toFixed(1)}GB`;
}

export default function DataSourcesPage() {
  const router = useRouter();
  const [draft, setDraft] = useState(emptyFilters);
  const [filters, setFilters] = useState(emptyFilters);
  const [result, setResult] = useState<DataSourceListResponse | null>(null);
  const [classificationTypes, setClassificationTypes] = useState<ClassificationType[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageModal, setPageModal] = useState(false);
  const [deleteRows, setDeleteRows] = useState<DataSource[]>([]);

  const load = useCallback(async (nextFilters = filters) => {
    setLoading(true);
    try {
      const data = await fetchDataSources(nextFilters);
      setResult(data);
      setSelected(new Set());
      setError(null);
    } catch (err) {
      if (err instanceof DataSourcesApiError && err.code === "PAGE_NOT_FOUND") setPageModal(true);
      else setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    Promise.all([fetchDataSourceTypes(), fetchCategories()])
      .then(([types, categoryResult]) => { setClassificationTypes(types); setCategories(categoryResult.items); })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const rows = result?.items ?? [];
  const allSelected = rows.length > 0 && rows.every((row) => selected.has(row.id));
  const someSelected = rows.some((row) => selected.has(row.id));
  const selectedRows = rows.filter((row) => selected.has(row.id));
  const typeMap = useMemo(() => Object.fromEntries(classificationTypes.map((type) => [type.type_code, type])), [classificationTypes]);

  const applySearch = () => {
    const next = { ...draft, page: 1, sort: filters.sort, order: filters.order, page_size: filters.page_size };
    setFilters(next);
  };
  const changeSort = (sort: SortColumn) => {
    setFilters((current) => ({ ...current, sort, order: current.sort === sort && current.order === "asc" ? "desc" : "asc", page: 1 }));
  };
  const changePage = (page: number) => setFilters((current) => ({ ...current, page }));
  const replaceRow = (row: DataSource) => setResult((current) => current ? ({ ...current, items: current.items.map((item) => item.id === row.id ? row : item) }) : current);

  const updateToggle = async (row: DataSource, field: "answer" | "reference", value: boolean) => {
    const previous = row;
    replaceRow({ ...row, [field === "answer" ? "answer_source_enabled" : "reference_link_visible"]: value });
    try {
      const updated = field === "answer"
        ? await updateAnswerSource(row.id, value, row.version)
        : await updateReferenceLink(row.id, value, row.version);
      replaceRow(updated);
      setError(null);
    } catch (err) {
      replaceRow(previous);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const confirmDelete = async () => {
    if (!deleteRows.length) return;
    setBusy(true);
    try {
      if (deleteRows.length === 1) await deleteDataSource(deleteRows[0].id, deleteRows[0].version);
      else await bulkDeleteDataSources(deleteRows.map((row) => ({ id: row.id, version: row.version })));
      setDeleteRows([]);
      await load(filters);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const download = async () => {
    setBusy(true);
    try {
      const blob = await exportDataSources(filters);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      const now = new Date();
      const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}`;
      anchor.download = `datasource${stamp}.xlsx`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AdminLayout activeMenu="data-sources" contentWidth="wide" contentAlign="start" onNavigate={(href) => router.push(href)}>
      <div className={styles.page}>
        <PageHeader title="データソース一覧" actions={<div className={styles.topActions}>
          <Button variant="secondary" icon={<AdminIcon name="list" size={18} />} onClick={() => router.push("/categories")}>カテゴリを設定する</Button>
          <Button variant="secondary" icon={<AdminIcon name="edit" size={18} />} onClick={() => router.push("/data-source-types")}>種別を設定する</Button>
          <Button variant="download" icon={<AdminIcon name="download" size={18} />} onClick={download} disabled={busy}>一覧をダウンロード</Button>
          <Button variant="secondary" disabled title="MVPでは未実装です">一覧を一括更新（未実装）</Button>
        </div>} />
        <div className={styles.summary}>
          <span>データソース数 {result?.total_count ?? 0}件</span>
          <span>サイズ {formatBytes(result?.total_size_bytes ?? 0)}</span>
        </div>
        <div className={styles.addActions}>
          <Button className={styles.primaryAction} variant="primary" icon={<AdminIcon name="plus" size={18} />} onClick={() => router.push("/data-sources/files/new")}>ファイル追加</Button>
          <Button className={styles.primaryAction} variant="primary" icon={<AdminIcon name="plus" size={18} />} onClick={() => router.push("/data-sources/websites/new")}>Webサイト追加</Button>
        </div>

        <div className={styles.filterGrid}>
          <FormField label="キーワード" wrapperClassName={styles.keyword} placeholder="キーワードを入力" value={draft.keyword} onChange={(event) => setDraft({ ...draft, keyword: event.target.value })} />
          <SelectField label="形式" value={draft.format} onChange={(event) => setDraft({ ...draft, format: event.target.value })}><option value="">すべて</option>{["pdf","doc","docx","xls","xlsx","ppt","pptx","txt","csv","Web"].map((value) => <option key={value}>{value}</option>)}</SelectField>
          <SelectField label="状態" value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}><option value="">すべて</option>{Object.entries(statusLabels).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</SelectField>
          <CategorySelectField label="カテゴリ" wrapperClassName={styles.category} categories={categories} emptyLabel="すべて" value={draft.category_id} onChange={(event) => setDraft({ ...draft, category_id: event.target.value })} />
          {["TYPE_1","TYPE_2","TYPE_3"].map((code, index) => {
            const key = `type_${index + 1}_value_id` as "type_1_value_id" | "type_2_value_id" | "type_3_value_id";
            const type = typeMap[code];
            return <SelectField key={code} label={type?.display_label ?? `種別${index + 1}`} value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}><option value="">すべて</option>{type?.values.map((value) => <option key={value.id} value={value.id}>{value.value_name}</option>)}</SelectField>;
          })}
          <SelectField label="回答ソース" value={draft.answer_source_enabled} onChange={(event) => setDraft({ ...draft, answer_source_enabled: event.target.value })}><option value="">すべて</option><option value="true">有効</option><option value="false">無効</option></SelectField>
          <SelectField label="優先度" value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value })}><option value="">すべて</option><option value="HIGH">高</option><option value="MEDIUM">中</option><option value="LOW">低</option></SelectField>
          <SelectField label="参照リンク" value={draft.reference_link_visible} onChange={(event) => setDraft({ ...draft, reference_link_visible: event.target.value })}><option value="">すべて</option><option value="true">表示</option><option value="false">非表示</option></SelectField>
          <div className={styles.filterButtonWrap}><Button className={styles.searchButton} variant="secondary" onClick={applySearch} icon={<AdminIcon name="search" size={18} />}>絞り込み検索</Button></div>
        </div>

        <div className={styles.bulkBar}>
          <div className={styles.bulkDelete}><Checkbox aria-label="表示中ページを全選択" checked={allSelected} indeterminate={!allSelected && someSelected} onChange={(event) => setSelected(event.target.checked ? new Set(rows.map((row) => row.id)) : new Set())} />選択したデータソースを<Button variant="danger" onClick={() => setDeleteRows(selectedRows)} disabled={!selectedRows.length}>削除</Button></div>
          <div className={styles.countControls}><span>全 {result?.total_count ?? 0}件</span><select aria-label="表示件数" className={styles.pageSize} value={filters.page_size} onChange={(event) => setFilters((current) => ({ ...current, page_size: Number(event.target.value), page: 1 }))}>{[10,20,50,100].map((value) => <option key={value}>{value}</option>)}</select><span>件ずつ表示</span></div>
        </div>
        {error && <div className={styles.error} role="alert">{error}</div>}

        {loading ? <div className={styles.loading}>読み込み中...</div> : <>
          <TableFrame className={styles.tableFrame}><Table className={styles.dataTable}>
            <thead><TableRow>
              <TableHeaderCell className={styles.checkColumn}><Checkbox aria-label="表示中ページを全選択" checked={allSelected} indeterminate={!allSelected && someSelected} onChange={(event) => setSelected(event.target.checked ? new Set(rows.map((row) => row.id)) : new Set())} /></TableHeaderCell>
              <TableHeaderCell className={styles.idColumn}><SortableHeader direction={filters.sort === "id" ? filters.order : null} onClick={() => changeSort("id")}>ID</SortableHeader></TableHeaderCell>
              <TableHeaderCell className={styles.titleColumn}><SortableHeader direction={filters.sort === "title" ? filters.order : null} onClick={() => changeSort("title")}>タイトル／ファイル名／URL</SortableHeader></TableHeaderCell>
              <TableHeaderCell className={styles.formatColumn}>形式</TableHeaderCell><TableHeaderCell className={styles.statusColumn}>状態</TableHeaderCell><TableHeaderCell className={styles.categoryColumn}>カテゴリ</TableHeaderCell><TableHeaderCell className={styles.classificationColumn}>種別</TableHeaderCell><TableHeaderCell className={styles.sizeColumn}>サイズ<br/>文字数</TableHeaderCell><TableHeaderCell className={styles.answerColumn}>回答ソース<br/>優先度</TableHeaderCell><TableHeaderCell className={styles.referenceColumn}>参照リンク</TableHeaderCell>
              <TableHeaderCell className={styles.dateColumn}><SortableHeader direction={filters.sort === "updated_at" ? filters.order : null} onClick={() => changeSort("updated_at")}>更新日時</SortableHeader></TableHeaderCell><TableHeaderCell className={styles.actionsColumn}>操作</TableHeaderCell>
            </TableRow></thead>
            <tbody>{rows.map((row) => {
              const location = row.file?.file_name ?? row.website?.url ?? "";
              return <TableRow key={row.id}>
                <TableCell className={styles.checkColumn}><Checkbox aria-label={`${row.title}を選択`} checked={selected.has(row.id)} onChange={(event) => setSelected((current) => { const next = new Set(current); event.target.checked ? next.add(row.id) : next.delete(row.id); return next; })} /></TableCell>
                <TableCell className={styles.idColumn}>{row.id}</TableCell>
                <TableCell className={styles.titleColumn}><span className={styles.title}>{row.title}</span>{row.website ? <a className={`${styles.location} ${styles.locationLink}`} href={location} target="_blank" rel="noreferrer">{location}</a> : <span className={styles.location}>{location}</span>}</TableCell>
                <TableCell className={styles.formatColumn}>{row.format}</TableCell><TableCell className={styles.statusColumn}><StatusBadge tone={statusTones[row.status]}>{statusLabels[row.status]}</StatusBadge></TableCell><TableCell className={styles.categoryColumn}>{row.category_name ?? "－"}</TableCell>
                <TableCell className={styles.classificationColumn}><div className={styles.classificationTags}>{row.classifications.map((item) => <span className={styles.classificationTag} key={item.type_code}>{item.display_label} {item.value_name}</span>)}</div></TableCell>
                <TableCell className={`${styles.sizeColumn} ${styles.numbers}`}>{formatBytes(row.size_bytes)}<br/>{row.character_count?.toLocaleString() ?? "－"}</TableCell>
                <TableCell className={styles.answerColumn}><ToggleSwitch checked={row.answer_source_enabled} checkedLabel="有効" uncheckedLabel="無効" onChange={(value) => updateToggle(row, "answer", value)} /><div className={styles.priority}>優先度: {priorityLabels[row.priority]}</div></TableCell>
                <TableCell className={styles.referenceColumn}><ToggleSwitch checked={row.reference_link_visible} checkedLabel="表示" uncheckedLabel="非表示" onChange={(value) => updateToggle(row, "reference", value)} /></TableCell>
                <TableCell className={styles.dateColumn}>{new Date(row.updated_at).toLocaleString("ja-JP", { year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit" })}</TableCell>
                <TableCell className={styles.actionsColumn}><div className={styles.rowActions}><Button className={`${styles.rowAction} ${styles.disabledAction}`} variant="text" disabled title={row.source_type === "FILE" ? "実ファイルダウンロードは未実装です" : "Web再取得は未実装です"}>{row.source_type === "FILE" ? "取得" : "更新"}</Button><Button className={styles.rowAction} variant="text" onClick={() => router.push(`/data-sources/${row.id}/${row.source_type === "FILE" ? "file" : "website"}/edit`)}>編集</Button><Button className={styles.rowAction} variant="text" focusTone="danger" onClick={() => setDeleteRows([row])}>削除</Button></div></TableCell>
              </TableRow>;
            })}</tbody>
          </Table></TableFrame>
          <div className={styles.paginationWrap}><Pagination page={result?.page ?? 1} totalPages={result?.total_pages ?? 0} onPageChange={changePage} onInvalidPage={changePage} /></div>
        </>}
      </div>

      <Modal open={Boolean(deleteRows.length)} title={deleteRows.length > 1 ? "データソースの一括削除" : "データソースの削除"} variant="danger" confirmLabel="削除する" busy={busy} error={error} onConfirm={confirmDelete} onClose={() => setDeleteRows([])}>
        <p className={styles.modalText}>{deleteRows.length > 1 ? `${deleteRows.length}件のデータを削除します。一度削除すると元に戻せません。` : `「${deleteRows[0]?.title ?? ""}」を削除します。一度削除すると元に戻せません。`}<br/>本当に削除しますか？</p>
      </Modal>
      <Modal open={pageModal} title="ページがありません" cancelLabel="閉じる" onClose={() => setPageModal(false)}>指定されたページは存在しません。</Modal>
    </AdminLayout>
  );
}
