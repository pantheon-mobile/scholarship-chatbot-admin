"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  AdminIcon, AdminLayout, Button, Checkbox, FormField, Modal, PageHeader, Pagination,
  SelectField, SortableHeader, StatusBadge, Table, TableCell, TableFrame, TableHeaderCell, TableRow,
} from "@/components/admin";
import { FaqReferenceModal } from "@/components/faqs/FaqReferenceModal";
import { useAuth } from "@/components/auth/AuthProvider";
import { fetchFaqClassifications } from "@/lib/faqClassificationsApi";
import { isSystemAdmin } from "@/lib/permissions";
import { bulkDeleteFaqs, deleteFaq, downloadFaqImportTemplate, exportFaqs, fetchFaq, fetchFaqs, importFaqs } from "@/lib/faqsApi";
import { Faq, FaqApiError, FaqDetail, FaqFilters, FaqImportRowError, FaqListResponse, FaqSortColumn } from "@/types/faq";
import { FaqClassificationType } from "@/types/faqClassification";
import styles from "./page.module.css";

const emptyFilters: FaqFilters = {
  keyword: "", classification_1_value_id: "", classification_2_value_id: "",
  classification_3_value_id: "", classification_4_value_id: "", chat_enabled: "",
  sort: "updated_at", order: "desc", page: 1, page_size: 10,
};

export default function FaqsPage() {
  const router = useRouter();
  const auth = useAuth();
  const [draft, setDraft] = useState(emptyFilters);
  const [filters, setFilters] = useState(emptyFilters);
  const [result, setResult] = useState<FaqListResponse | null>(null);
  const [classificationTypes, setClassificationTypes] = useState<FaqClassificationType[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleteRows, setDeleteRows] = useState<Faq[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageModal, setPageModal] = useState(false);
  const [notice, setNotice] = useState<{ title: string; message: string } | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importErrors, setImportErrors] = useState<FaqImportRowError[]>([]);
  const [templateBusy, setTemplateBusy] = useState(false);
  const [referenceId, setReferenceId] = useState<number | null>(null);
  const [referenceDetail, setReferenceDetail] = useState<FaqDetail | null>(null);
  const [referenceLoading, setReferenceLoading] = useState(false);
  const [referenceError, setReferenceError] = useState<string | null>(null);
  const [deleteFromReference, setDeleteFromReference] = useState(false);
  const referenceRequestRef = useRef(0);
  const referenceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const safeFocusRef = useRef<HTMLButtonElement | null>(null);
  const importFileInputRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(async (nextFilters = filters) => {
    setLoading(true);
    try {
      setResult(await fetchFaqs(nextFilters));
      setSelected(new Set());
      setError(null);
    } catch (reason) {
      if (reason instanceof FaqApiError && reason.code === "PAGE_NOT_FOUND") setPageModal(true);
      else setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    fetchFaqClassifications().then(setClassificationTypes).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  const rows = result?.items ?? [];
  const selectedRows = rows.filter((row) => selected.has(row.id));
  const allSelected = rows.length > 0 && rows.every((row) => selected.has(row.id));
  const someSelected = rows.some((row) => selected.has(row.id));
  const typeMap = useMemo(() => Object.fromEntries(classificationTypes.map((type) => [type.type_code, type])), [classificationTypes]);

  const selectPage = (checked: boolean) => setSelected(checked ? new Set(rows.map((row) => row.id)) : new Set());
  const applySearch = () => setFilters({ ...draft, page: 1, sort: filters.sort, order: filters.order, page_size: filters.page_size });
  const changeSort = (sort: FaqSortColumn) => setFilters((current) => ({
    ...current, sort, order: current.sort === sort && current.order === "asc" ? "desc" : "asc", page: 1,
  }));

  const confirmDelete = async () => {
    if (!deleteRows.length) return;
    const targets = [...deleteRows];
    const startedFromReference = deleteFromReference;
    setBusy(true);
    try {
      if (targets.length === 1) await deleteFaq(targets[0].id, targets[0].version);
      else await bulkDeleteFaqs(targets.map(({ id, version }) => ({ id, version })));
      setDeleteRows([]);
      const visibleDeleted = targets.filter((target) => rows.some((row) => row.id === target.id)).length;
      if (filters.page > 1 && visibleDeleted === rows.length) {
        setFilters((current) => ({ ...current, page: current.page - 1 }));
      } else {
        await load(filters);
      }
      if (startedFromReference) {
        const target = safeFocusRef.current;
        window.setTimeout(() => target?.focus(), 0);
        referenceTriggerRef.current = null;
      }
      setDeleteFromReference(false);
    } catch (reason) {
      setError(reason instanceof FaqApiError && reason.code === "FAQ_VERSION_CONFLICT"
        ? "他の操作で情報が更新されています。再読み込みしてください。"
        : reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  };

  const openReference = async (faqId: number, trigger: HTMLButtonElement) => {
    if (referenceLoading || referenceId !== null) return;
    const requestId = referenceRequestRef.current + 1;
    referenceRequestRef.current = requestId;
    referenceTriggerRef.current = trigger;
    setReferenceId(faqId);
    setReferenceDetail(null);
    setReferenceError(null);
    setReferenceLoading(true);
    try {
      const detail = await fetchFaq(faqId);
      if (referenceRequestRef.current === requestId) setReferenceDetail(detail);
    } catch (reason) {
      if (referenceRequestRef.current === requestId) {
        setReferenceError(reason instanceof Error ? reason.message : "FAQの取得に失敗しました。");
      }
    } finally {
      if (referenceRequestRef.current === requestId) setReferenceLoading(false);
    }
  };

  const closeReference = () => {
    if (busy) return;
    referenceRequestRef.current += 1;
    setReferenceId(null);
    setReferenceDetail(null);
    setReferenceError(null);
    setReferenceLoading(false);
  };

  const editReference = () => {
    if (!referenceDetail || busy) return;
    const faqId = referenceDetail.id;
    closeReference();
    router.push(`/faqs/${faqId}/edit`);
  };

  const deleteReference = () => {
    if (!referenceDetail || busy) return;
    const target = referenceDetail;
    closeReference();
    setError(null);
    setDeleteFromReference(true);
    setDeleteRows([target]);
  };

  const closeDeleteModal = () => {
    if (busy) return;
    setDeleteRows([]);
    setError(null);
    if (deleteFromReference) {
      const target = referenceTriggerRef.current;
      window.setTimeout(() => {
        if (target?.isConnected) target.focus();
        else safeFocusRef.current?.focus();
      }, 0);
    }
    setDeleteFromReference(false);
  };

  const download = async () => {
    setBusy(true);
    try {
      const blob = await exportFaqs(filters);
      const now = new Date();
      const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}`;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `faq${stamp}.xlsx`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  };

  const downloadTemplate = async () => {
    if (templateBusy) return;
    setTemplateBusy(true);
    try {
      const blob = await downloadFaqImportTemplate();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "faq_import_template.xlsx";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setTemplateBusy(false); }
  };

  const closeImport = () => {
    if (importBusy) return;
    setImportOpen(false);
    setImportFile(null);
    setImportError(null);
    setImportErrors([]);
    if (importFileInputRef.current) importFileInputRef.current.value = "";
  };

  const selectImportFile = (file: File | null) => {
    setImportError(null);
    setImportErrors([]);
    if (file && !file.name.toLowerCase().endsWith(".xlsx")) {
      setImportFile(null);
      setImportError("xlsx形式のファイルを選択してください。");
      return;
    }
    setImportFile(file);
  };

  const executeImport = async () => {
    if (!importFile || importBusy) return;
    setImportBusy(true);
    setImportError(null);
    setImportErrors([]);
    try {
      const imported = await importFaqs(importFile);
      const refreshedFilters = { ...filters, page: 1, sort: "updated_at" as const, order: "desc" as const };
      if (filters.page !== 1 || filters.sort !== "updated_at" || filters.order !== "desc") setFilters(refreshedFilters);
      else await load(refreshedFilters);
      setImportOpen(false);
      setImportFile(null);
      if (importFileInputRef.current) importFileInputRef.current.value = "";
      setNotice({ title: "FAQ一括登録／更新完了", message: `${imported.created_count}件を登録、${imported.updated_count}件を更新しました。` });
    } catch (reason) {
      setImportError(reason instanceof Error ? reason.message : String(reason));
      setImportErrors(reason instanceof FaqApiError ? reason.errors : []);
    } finally { setImportBusy(false); }
  };

  return <AdminLayout activeMenu="faq" contentWidth="wide" contentAlign="start" onNavigate={(href) => router.push(href)}>
    <div className={styles.page}>
      <PageHeader title="FAQ一覧" actions={<div className={styles.topActions}>
        {isSystemAdmin(auth.user?.role ?? "admin") && <Button variant="secondary" icon={<AdminIcon name="list" size={18} />} onClick={() => router.push("/faq-classifications")}>区分を設定する</Button>}
        <Button variant="download" icon={<AdminIcon name="download" size={18} />} onClick={download} disabled={busy}>一覧をダウンロード</Button>
        <Button variant="secondary" icon={<AdminIcon name="upload" size={18} />} onClick={() => setImportOpen(true)} disabled={importBusy}>FAQを一括登録／更新</Button>
        <Button variant="text" onClick={downloadTemplate} disabled={templateBusy}>{templateBusy ? "ダウンロード中..." : "フォーマットをダウンロード"}</Button>
      </div>} />
      <div className={styles.summary}>FAQ数　{result?.total_count ?? 0}件</div>
      <Button ref={safeFocusRef} className={styles.addButton} variant="primary" icon={<AdminIcon name="plus" size={18} />} onClick={() => router.push("/faqs/new")}>FAQ新規追加</Button>

      <div className={styles.filterGrid}>
        <FormField label="キーワード" wrapperClassName={styles.keyword} placeholder="質問／回答のキーワードを入力" value={draft.keyword} onChange={(event) => setDraft({ ...draft, keyword: event.target.value })} />
        {[1, 2, 3, 4].map((index) => {
          const type = typeMap[`FAQ_TYPE_${index}`];
          const key = `classification_${index}_value_id` as keyof Pick<FaqFilters, "classification_1_value_id" | "classification_2_value_id" | "classification_3_value_id" | "classification_4_value_id">;
          return <SelectField key={index} label={type?.display_label ?? `区分${index}`} value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}>
            <option value="">すべて</option>{type?.values.map((value) => <option key={value.id} value={value.id}>{value.value_name}</option>)}
          </SelectField>;
        })}
        <SelectField label="チャット利用" value={draft.chat_enabled} onChange={(event) => setDraft({ ...draft, chat_enabled: event.target.value })}>
          <option value="">すべて</option><option value="true">公開</option><option value="false">非公開</option>
        </SelectField>
        <div className={styles.filterButtonWrap}><Button variant="secondary" icon={<AdminIcon name="search" size={18} />} onClick={applySearch}>絞り込み検索</Button></div>
      </div>

      <div className={styles.bulkBar}>
        <div className={styles.bulkDelete}><Checkbox aria-label="表示中ページを全選択" checked={allSelected} indeterminate={!allSelected && someSelected} onChange={(event) => selectPage(event.target.checked)} />選択したFAQを<Button variant="danger" disabled={!selectedRows.length} onClick={() => setDeleteRows(selectedRows)}>削除</Button></div>
        <div className={styles.countControls}><span>全 {result?.total_count ?? 0}件</span><select aria-label="表示件数" className={styles.pageSize} value={filters.page_size} onChange={(event) => setFilters((current) => ({ ...current, page_size: Number(event.target.value), page: 1 }))}>{[10,20,50,100].map((value) => <option key={value}>{value}</option>)}</select><span>件ずつ表示</span></div>
      </div>
      {error && !deleteRows.length && <div className={styles.error} role="alert">{error}</div>}

      {loading ? <div className={styles.loading}>読み込み中...</div> : <>
        <TableFrame className={styles.tableFrame}><Table className={styles.faqTable}>
          <thead><TableRow>
            <TableHeaderCell className={styles.checkColumn}><Checkbox aria-label="表示中ページを全選択" checked={allSelected} indeterminate={!allSelected && someSelected} onChange={(event) => selectPage(event.target.checked)} /></TableHeaderCell>
            <TableHeaderCell className={styles.idColumn}><SortableHeader direction={filters.sort === "id" ? filters.order : null} onClick={() => changeSort("id")}>ID</SortableHeader></TableHeaderCell>
            <TableHeaderCell className={styles.questionColumn}>質問</TableHeaderCell><TableHeaderCell className={styles.answerColumn}>回答</TableHeaderCell>
            {[1,2,3,4].map((index) => <TableHeaderCell className={styles.classificationColumn} key={index}>{typeMap[`FAQ_TYPE_${index}`]?.display_label ?? `区分${index}`}</TableHeaderCell>)}
            <TableHeaderCell className={styles.chatColumn}>チャット利用</TableHeaderCell>
            <TableHeaderCell className={styles.dateColumn}><SortableHeader direction={filters.sort === "updated_at" ? filters.order : null} onClick={() => changeSort("updated_at")}>更新日時</SortableHeader></TableHeaderCell>
            <TableHeaderCell className={styles.actionsColumn}>操作</TableHeaderCell>
          </TableRow></thead>
          <tbody>{rows.length === 0 ? <TableRow><TableCell colSpan={11} className={styles.empty}>FAQは登録されていません。</TableCell></TableRow> : rows.map((row) => {
            const values = Object.fromEntries(row.classifications.map((item) => [item.type_code, item.value_name]));
            return <TableRow key={row.id}>
              <TableCell className={styles.checkColumn}><Checkbox aria-label={`${row.question}を選択`} checked={selected.has(row.id)} onChange={(event) => setSelected((current) => { const next = new Set(current); event.target.checked ? next.add(row.id) : next.delete(row.id); return next; })} /></TableCell>
              <TableCell className={styles.idColumn}>{row.id}</TableCell>
              <TableCell className={styles.questionColumn}><div className={styles.longText}>{row.question}</div></TableCell>
              <TableCell className={styles.answerColumn}><div className={styles.longText}>{row.answer}</div></TableCell>
              {[1,2,3,4].map((index) => <TableCell className={styles.classificationColumn} key={index}>{values[`FAQ_TYPE_${index}`] ?? "－"}</TableCell>)}
              <TableCell className={styles.chatColumn}><StatusBadge tone={row.chat_enabled ? "success" : "neutral"}>{row.chat_enabled ? "公開" : "非公開"}</StatusBadge></TableCell>
              <TableCell className={styles.dateColumn}>{new Date(row.updated_at).toLocaleString("ja-JP", { year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit" })}</TableCell>
              <TableCell className={styles.actionsColumn}><div className={styles.rowActions}>
                <Button variant="text" onClick={(event) => openReference(row.id, event.currentTarget)}>参照</Button>
                <Button variant="text" onClick={() => router.push(`/faqs/${row.id}/edit`)}>編集</Button>
                <Button variant="text" focusTone="danger" onClick={() => { setError(null); setDeleteRows([row]); }}>削除</Button>
              </div></TableCell>
            </TableRow>;
          })}</tbody>
        </Table></TableFrame>
        <div className={styles.paginationWrap}><Pagination page={result?.page ?? 1} totalPages={result?.total_pages ?? 0} onPageChange={(page) => setFilters((current) => ({ ...current, page }))} onInvalidPage={() => setPageModal(true)} /></div>
      </>}
    </div>

    <FaqReferenceModal
      open={referenceId !== null}
      detail={referenceDetail}
      classificationTypes={classificationTypes}
      loading={referenceLoading}
      busy={busy}
      error={referenceError}
      onClose={closeReference}
      onEdit={editReference}
      onDelete={deleteReference}
    />
    <Modal open={Boolean(deleteRows.length)} title={deleteRows.length > 1 ? "FAQの一括削除" : "FAQの削除"} variant="danger" confirmLabel="削除する" busy={busy} error={error} onConfirm={confirmDelete} onClose={closeDeleteModal}>
      {deleteRows.length > 1 ? `選択した${deleteRows.length}件のFAQを削除します。` : `FAQ「${deleteRows[0]?.question ?? ""}」を削除します。`}<br />この操作は元に戻せません。<br />本当に削除しますか？
    </Modal>
    <Modal open={pageModal} title="ページがありません" cancelLabel="閉じる" onClose={() => setPageModal(false)}>指定されたページは存在しません。</Modal>
    <Modal
      open={importOpen}
      title="FAQを一括登録／更新"
      busy={importBusy}
      closeOnBackdrop={!importBusy}
      closeOnEscape={!importBusy}
      onClose={closeImport}
      footer={<>
        <Button className={styles.importFooterButton} variant="secondary" onClick={closeImport} disabled={importBusy}>キャンセル</Button>
        <Button className={styles.importFooterButton} variant="primary" onClick={executeImport} disabled={importBusy || !importFile}>{importBusy ? "処理中..." : "登録／更新する"}</Button>
      </>}
    >
      <div className={styles.importBody}>
        <p className={styles.importHelp}>FAQ一括登録／更新用のxlsxファイルを選択してください。</p>
        <Button variant="secondary" onClick={() => importFileInputRef.current?.click()} disabled={importBusy}>ファイルを選択</Button>
        <input
          ref={importFileInputRef}
          className={styles.hiddenFileInput}
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          aria-label="FAQ一括登録／更新ファイル"
          disabled={importBusy}
          onClick={(event) => { event.currentTarget.value = ""; }}
          onChange={(event) => selectImportFile(event.target.files?.[0] ?? null)}
        />
        <div className={styles.importFileName}>{importFile ? importFile.name : "ファイルが選択されていません。"}</div>
        {importError && <div className={styles.importError} role="alert">{importError}</div>}
        {importErrors.length > 0 && <ul className={styles.importErrorList} aria-label="Excel入力エラー">
          {importErrors.map((item, index) => <li key={`${item.row}-${item.column}-${item.code}-${index}`}>行{item.row}・{item.column}: {item.message}</li>)}
        </ul>}
      </div>
    </Modal>
    <Modal open={Boolean(notice)} title={notice?.title ?? "完了"} cancelLabel="閉じる" onClose={() => setNotice(null)}>{notice?.message}</Modal>
  </AdminLayout>;
}
