"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { closestCenter, DndContext, DragEndEvent, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { arrayMove, SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import {
  AdminIcon,
  AdminLayout,
  Button,
  FormField,
  Modal,
  PageHeader,
  Table,
  TableActions,
  TableCell,
  TableFrame,
  TableHeaderCell,
  TableRow,
} from "@/components/admin";
import {
  addFaqClassificationValue,
  deleteFaqClassificationValue,
  exportFaqClassifications,
  fetchFaqClassifications,
  reorderFaqClassificationValues,
  updateFaqClassificationLabel,
  updateFaqClassificationValue,
} from "@/lib/faqClassificationsApi";
import { FaqClassificationType, FaqClassificationValue } from "@/types/faqClassification";
import styles from "./page.module.css";

type DeleteTarget = { typeId: number; value: FaqClassificationValue };

type SortableValueRowProps = {
  value: FaqClassificationValue;
  editingValue?: string;
  busy: boolean;
  onEdit: () => void;
  onChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
  onDelete: () => void;
};

function SortableValueRow({ value, editingValue, busy, onEdit, onChange, onSave, onCancel, onDelete }: SortableValueRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: value.id });
  const editing = editingValue !== undefined;
  return <TableRow
    ref={setNodeRef}
    className={`${styles.valueRow} ${isDragging ? styles.dragging : ""}`}
    style={{ transform: CSS.Transform.toString(transform), transition }}
  >
    <TableCell className={styles.handleCell}>
      <button
        type="button"
        className={styles.dragHandle}
        aria-label={`${value.value_name}を並び替え`}
        disabled={busy || editing}
        {...attributes}
        {...listeners}
      >
        <AdminIcon name="grip" size={27} />
      </button>
    </TableCell>
    <TableCell className={styles.valueCell}>
      {editing ? <FormField
        compact
        inputClassName={styles.valueInput}
        aria-label={`${value.value_name}の区分値`}
        value={editingValue}
        onChange={(event) => onChange(event.target.value)}
      /> : value.value_name}
    </TableCell>
    <TableCell className={styles.actionCell}>
      <TableActions>
        {editing ? <>
          <Button variant="text" icon={<AdminIcon name="edit" size={17} />} onClick={onSave} disabled={busy}>更新</Button>
          <Button variant="text" focusTone="danger" className={styles.dangerAction} onClick={onCancel} disabled={busy}>キャンセル</Button>
        </> : <>
          <Button variant="text" icon={<AdminIcon name="edit" size={17} />} onClick={onEdit} disabled={busy}>編集</Button>
          <Button variant="text" focusTone="danger" className={styles.dangerAction} icon={<AdminIcon name="trash" size={17} />} onClick={onDelete} disabled={busy}>削除</Button>
        </>}
      </TableActions>
    </TableCell>
  </TableRow>;
}

export default function FaqClassificationsPage() {
  const router = useRouter();
  const [types, setTypes] = useState<FaqClassificationType[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingLabels, setEditingLabels] = useState<Record<number, string>>({});
  const [editingValues, setEditingValues] = useState<Record<number, string>>({});
  const [addingRows, setAddingRows] = useState<Record<number, string[]>>({});
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  useEffect(() => {
    fetchFaqClassifications()
      .then((items) => { setTypes(items); setError(null); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => setLoading(false));
  }, []);

  const hasPendingChanges = useMemo(
    () => Object.keys(editingLabels).length > 0 || Object.keys(editingValues).length > 0 || Object.values(addingRows).some((rows) => rows.length > 0),
    [editingLabels, editingValues, addingRows],
  );

  const replaceType = (updated: FaqClassificationType) => {
    setTypes((current) => current.map((type) => type.id === updated.id ? updated : type));
  };

  const navigate = (path: string) => {
    if (hasPendingChanges) setPendingNavigation(path);
    else router.push(path);
  };

  const saveLabel = async (type: FaqClassificationType) => {
    const label = editingLabels[type.id]?.trim() ?? "";
    if (!label) { setError("区分ラベルを入力してください。"); return; }
    try {
      setBusy(true);
      replaceType(await updateFaqClassificationLabel(type.id, label, type.version));
      setEditingLabels((current) => { const next = { ...current }; delete next[type.id]; return next; });
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  };

  const cancelLabel = (typeId: number) => setEditingLabels((current) => {
    const next = { ...current }; delete next[typeId]; return next;
  });

  const addRow = (typeId: number) => setAddingRows((current) => ({ ...current, [typeId]: [...(current[typeId] ?? []), ""] }));
  const changeAddRow = (typeId: number, index: number, value: string) => setAddingRows((current) => ({
    ...current, [typeId]: current[typeId].map((item, itemIndex) => itemIndex === index ? value : item),
  }));
  const cancelAddRow = (typeId: number, index: number) => setAddingRows((current) => ({
    ...current, [typeId]: current[typeId].filter((_, itemIndex) => itemIndex !== index),
  }));

  const registerValue = async (typeId: number, index: number) => {
    const value = addingRows[typeId]?.[index]?.trim() ?? "";
    if (!value) { setError("区分値を入力してください。"); return; }
    try {
      setBusy(true);
      replaceType(await addFaqClassificationValue(typeId, value));
      cancelAddRow(typeId, index);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  };

  const saveValue = async (typeId: number, value: FaqClassificationValue) => {
    const name = editingValues[value.id]?.trim() ?? "";
    if (!name) { setError("区分値を入力してください。"); return; }
    try {
      setBusy(true);
      replaceType(await updateFaqClassificationValue(typeId, value.id, name, value.version));
      setEditingValues((current) => { const next = { ...current }; delete next[value.id]; return next; });
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  };

  const cancelValue = (valueId: number) => setEditingValues((current) => {
    const next = { ...current }; delete next[valueId]; return next;
  });

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      setBusy(true);
      await deleteFaqClassificationValue(deleteTarget.typeId, deleteTarget.value.id, deleteTarget.value.version);
      setTypes(await fetchFaqClassifications());
      setDeleteTarget(null);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  };

  const handleDragEnd = async (typeId: number, event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const type = types.find((item) => item.id === typeId);
    if (!type) return;
    const oldIndex = type.values.findIndex((item) => item.id === Number(active.id));
    const newIndex = type.values.findIndex((item) => item.id === Number(over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    const previousValues = type.values;
    const reordered = arrayMove(previousValues, oldIndex, newIndex);
    setTypes((current) => current.map((item) => item.id === typeId ? { ...item, values: reordered } : item));
    try {
      setBusy(true);
      replaceType(await reorderFaqClassificationValues(typeId, reordered.map(({ id, version }) => ({ id, version }))));
      setError(null);
    } catch (reason) {
      setTypes((current) => current.map((item) => item.id === typeId ? { ...item, values: previousValues } : item));
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  };

  const exportList = async () => {
    try {
      setBusy(true);
      const blob = await exportFaqClassifications();
      const now = new Date();
      const stamp = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0"), String(now.getHours()).padStart(2, "0"), String(now.getMinutes()).padStart(2, "0")].join("");
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `classification${stamp}.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  };

  return <AdminLayout activeMenu="faq" contentWidth="default" contentAlign="start" onNavigate={navigate}>
    <PageHeader title="区分設定" actions={<>
      <Button variant="secondary" icon={<AdminIcon name="back" size={19} />} onClick={() => navigate("/faqs")}>一覧に戻る</Button>
      <Button variant="download" icon={<AdminIcon name="download" size={20} />} onClick={exportList} disabled={busy}>一覧をダウンロード</Button>
    </>} />

    {error && !deleteTarget && <div className={styles.error} role="alert">{error}</div>}
    {loading ? <p className={styles.loading}>読み込み中...</p> : <div className={styles.typeList}>
      {types.map((type) => {
        const labelEditing = editingLabels[type.id] !== undefined;
        const additions = addingRows[type.id] ?? [];
        return <section className={styles.typeSection} key={type.id}>
          <TableFrame>
            <Table>
              <thead><TableRow>
                <TableHeaderCell colSpan={2}>
                  <span className={styles.fixedName}>{type.fixed_name}：</span>
                  {labelEditing ? <FormField
                    compact
                    wrapperClassName={styles.labelField}
                    inputClassName={styles.labelInput}
                    aria-label={`${type.fixed_name}の区分ラベル`}
                    value={editingLabels[type.id]}
                    onChange={(event) => setEditingLabels((current) => ({ ...current, [type.id]: event.target.value }))}
                  /> : type.display_label}
                </TableHeaderCell>
                <TableHeaderCell className={styles.actionCell}><TableActions>
                  {labelEditing ? <>
                    <Button variant="text" icon={<AdminIcon name="edit" size={17} />} onClick={() => saveLabel(type)} disabled={busy}>更新</Button>
                    <Button variant="text" focusTone="danger" className={styles.dangerAction} onClick={() => cancelLabel(type.id)} disabled={busy}>キャンセル</Button>
                  </> : <Button variant="text" icon={<AdminIcon name="edit" size={17} />} onClick={() => setEditingLabels((current) => ({ ...current, [type.id]: type.display_label }))} disabled={busy}>編集</Button>}
                </TableActions></TableHeaderCell>
              </TableRow></thead>
            </Table>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(event) => handleDragEnd(type.id, event)}>
              <SortableContext items={type.values.map((value) => value.id)} strategy={verticalListSortingStrategy}>
                <Table><tbody>
                  {type.values.length === 0 && additions.length === 0 && <TableRow><TableCell colSpan={3} className={styles.emptyCell}>区分値は登録されていません。</TableCell></TableRow>}
                  {type.values.map((value) => <SortableValueRow
                    key={value.id}
                    value={value}
                    editingValue={editingValues[value.id]}
                    busy={busy}
                    onEdit={() => setEditingValues((current) => ({ ...current, [value.id]: value.value_name }))}
                    onChange={(next) => setEditingValues((current) => ({ ...current, [value.id]: next }))}
                    onSave={() => saveValue(type.id, value)}
                    onCancel={() => cancelValue(value.id)}
                    onDelete={() => { setError(null); setDeleteTarget({ typeId: type.id, value }); }}
                  />)}
                  {additions.map((value, index) => <TableRow className={styles.addingRow} key={`new-${index}`}>
                    <TableCell className={styles.handleCell} />
                    <TableCell className={styles.valueCell}><FormField
                      compact autoFocus wrapperClassName={styles.valueField} inputClassName={styles.valueInput}
                      aria-label={`${type.fixed_name}の追加区分値`}
                      value={value}
                      onChange={(event) => changeAddRow(type.id, index, event.target.value)}
                    /></TableCell>
                    <TableCell className={styles.actionCell}><TableActions>
                      <Button variant="text" onClick={() => registerValue(type.id, index)} disabled={busy}>登録</Button>
                      <Button variant="text" focusTone="danger" className={styles.dangerAction} onClick={() => cancelAddRow(type.id, index)} disabled={busy}>キャンセル</Button>
                    </TableActions></TableCell>
                  </TableRow>)}
                </tbody></Table>
              </SortableContext>
            </DndContext>
          </TableFrame>
          <Button className={styles.addButton} variant="add" icon={<AdminIcon name="plus" size={21} />} onClick={() => addRow(type.id)} disabled={busy}>追加</Button>
        </section>;
      })}
    </div>}

    <Modal
      open={Boolean(deleteTarget)}
      title="区分値の削除"
      variant="danger"
      cancelLabel="キャンセル"
      confirmLabel="削除する"
      busy={busy}
      error={error}
      onConfirm={confirmDelete}
      onClose={() => { setDeleteTarget(null); setError(null); }}
    >
      区分「{deleteTarget?.value.value_name ?? ""}」を削除します。一度削除すると元に戻せません。
      <br />本当に削除しますか？
    </Modal>
    <Modal
      open={Boolean(pendingNavigation)}
      title="確認"
      cancelLabel="キャンセル"
      confirmLabel="破棄する"
      confirmVariant="danger"
      busy={busy}
      onConfirm={() => { const path = pendingNavigation; setPendingNavigation(null); if (path) router.push(path); }}
      onClose={() => setPendingNavigation(null)}
    >未保存の内容があります。このまま閉じると、保存していない内容が破棄されます。</Modal>
  </AdminLayout>;
}
