"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  addClassificationValue,
  deleteClassificationValue,
  exportClassificationTypes,
  fetchDataSourceTypes,
  reorderClassificationValues,
  updateClassificationValue,
  updateTypeLabel,
} from "@/lib/api";
import { ClassificationType } from "@/types/dataSourceTypes";
import {
  AdminLayout,
  AdminIcon,
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
import styles from "./page.module.css";

type DeleteTarget = { typeId: number; valueId: number; valueName: string; version: number };

const modalMessages = {
  deleteValue: {
    title: "種別値の削除",
    cancel: "キャンセル",
    confirm: "削除する",
    body: (valueName: string) => (
      <>
        種別「{valueName}」を削除します。一度削除すると元に戻せません。
        <br />
        本当に削除しますか？
      </>
    ),
  },
  discardChanges: {
    title: "確認",
    cancel: "キャンセル",
    confirm: "OK",
    body: "処理をキャンセルしてよろしいですか",
  },
} as const;

type SortableValueRowProps = {
  value: { id: number; value_name: string; version: number };
  editing: boolean;
  editingValue: string;
  saving: boolean;
  onEdit: () => void;
  onChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
  onDelete: () => void;
};

function SortableValueRow({
  value,
  editing,
  editingValue,
  saving,
  onEdit,
  onChange,
  onSave,
  onCancel,
  onDelete,
}: SortableValueRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: value.id });

  return (
    <TableRow
      ref={setNodeRef}
      className={`${styles.valueRow} ${isDragging ? styles.dragging : ""}`}
      style={{ transform: CSS.Transform.toString(transform), transition }}
    >
      <TableCell className={styles.handleCell}>
        <button
          type="button"
          className={styles.dragHandle}
          aria-label={`${value.value_name}を並び替え`}
          disabled={saving}
          {...attributes}
          {...listeners}
        >
          <AdminIcon name="grip" size={27} />
        </button>
      </TableCell>
      <TableCell className={styles.valueCell}>
        {editing ? (
          <FormField
            compact
            inputClassName={styles.valueInput}
            type="text"
            value={editingValue}
            maxLength={200}
            onChange={(event) => onChange(event.target.value)}
          />
        ) : (
          value.value_name
        )}
      </TableCell>
      <TableCell className={styles.actionCell}>
        <TableActions>
        {editing ? (
          <>
            <Button variant="text" icon={<AdminIcon name="edit" size={17} />} onClick={onSave} disabled={saving}>更新</Button>
            <Button variant="text" focusTone="danger" className={styles.dangerAction} onClick={onCancel} disabled={saving}>キャンセル</Button>
          </>
        ) : (
          <>
            <Button variant="text" icon={<AdminIcon name="edit" size={17} />} onClick={onEdit} disabled={saving}>編集</Button>
            <Button variant="text" focusTone="danger" className={styles.dangerAction} icon={<AdminIcon name="trash" size={17} />} onClick={onDelete} disabled={saving}>削除</Button>
          </>
        )}
        </TableActions>
      </TableCell>
    </TableRow>
  );
}

export default function DataSourceTypesPage() {
  const router = useRouter();
  const [types, setTypes] = useState<ClassificationType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingLabel, setEditingLabel] = useState<Record<number, string>>({});
  const [editingValue, setEditingValue] = useState<Record<number, string>>({});
  const [addingRows, setAddingRows] = useState<Record<number, string[]>>({});
  const [saving, setSaving] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setTypes(await fetchDataSourceTypes());
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const hasPendingChanges = useMemo(
    () => Object.keys(editingLabel).length > 0 || Object.keys(editingValue).length > 0 ||
      Object.values(addingRows).some((rows) => rows.length > 0),
    [editingLabel, editingValue, addingRows]
  );

  const navigateWithConfirmation = (path: string) => {
    if (hasPendingChanges) {
      setPendingNavigation(path);
    } else {
      router.push(path);
    }
  };

  const handleLabelSave = async (typeId: number) => {
    const type = types.find((item) => item.id === typeId);
    const newLabel = editingLabel[typeId]?.trim();
    if (!type || !newLabel) {
      setError("種別ラベルを入力してください。");
      return;
    }
    try {
      setSaving(true);
      const result = await updateTypeLabel(typeId, newLabel, type.version);
      setTypes((current) => current.map((item) => item.id === typeId ? result : item));
      setEditingLabel((current) => {
        const next = { ...current };
        delete next[typeId];
        return next;
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const cancelLabelEdit = (typeId: number) => setEditingLabel((current) => {
    const next = { ...current };
    delete next[typeId];
    return next;
  });

  const addRow = (typeId: number) => setAddingRows((current) => ({
    ...current,
    [typeId]: [...(current[typeId] || []), ""],
  }));

  const changeAddRow = (typeId: number, index: number, value: string) => setAddingRows((current) => ({
    ...current,
    [typeId]: current[typeId].map((item, itemIndex) => itemIndex === index ? value : item),
  }));

  const cancelAddRow = (typeId: number, index: number) => setAddingRows((current) => ({
    ...current,
    [typeId]: current[typeId].filter((_, itemIndex) => itemIndex !== index),
  }));

  const registerValue = async (typeId: number, index: number) => {
    const value = addingRows[typeId]?.[index]?.trim();
    if (!value) {
      setError("種別値を入力してください。");
      return;
    }
    try {
      setSaving(true);
      const result = await addClassificationValue(typeId, value);
      setTypes((current) => current.map((item) => item.id === typeId ? result : item));
      cancelAddRow(typeId, index);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const saveValue = async (typeId: number, valueId: number, version: number) => {
    const newValue = editingValue[valueId]?.trim();
    if (!newValue) {
      setError("種別値を入力してください。");
      return;
    }
    try {
      setSaving(true);
      const result = await updateClassificationValue(typeId, valueId, newValue, version);
      setTypes((current) => current.map((item) => item.id === typeId ? result : item));
      setEditingValue((current) => {
        const next = { ...current };
        delete next[valueId];
        return next;
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const cancelValueEdit = (valueId: number) => setEditingValue((current) => {
    const next = { ...current };
    delete next[valueId];
    return next;
  });

  const deleteValue = async () => {
    if (!deleteTarget) return;
    try {
      setSaving(true);
      await deleteClassificationValue(deleteTarget.typeId, deleteTarget.valueId, deleteTarget.version);
      setTypes(await fetchDataSourceTypes());
      setDeleteTarget(null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const exportList = async () => {
    try {
      const blob = await exportClassificationTypes();
      const now = new Date();
      const stamp = [
        now.getFullYear(),
        String(now.getMonth() + 1).padStart(2, "0"),
        String(now.getDate()).padStart(2, "0"),
        String(now.getHours()).padStart(2, "0"),
        String(now.getMinutes()).padStart(2, "0"),
      ].join("");
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `type${stamp}.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleDragEnd = async (typeId: number, event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const type = types.find((item) => item.id === typeId);
    if (!type) return;
    const oldIndex = type.values.findIndex((item) => item.id === Number(active.id));
    const newIndex = type.values.findIndex((item) => item.id === Number(over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(type.values, oldIndex, newIndex);
    setTypes((current) => current.map((item) => item.id === typeId ? { ...item, values: reordered } : item));
    try {
      setSaving(true);
      await reorderClassificationValues(typeId, reordered.map((value) => value.id));
      setError(null);
    } catch (err) {
      setTypes(await fetchDataSourceTypes());
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout activeMenu="data-sources" contentWidth="default" contentAlign="start" onNavigate={navigateWithConfirmation}>
      <PageHeader
        title="種別設定"
        actions={
          <>
            <Button variant="secondary" onClick={() => navigateWithConfirmation("/")} icon={<AdminIcon name="back" size={19} />}>一覧に戻る</Button>
            <Button variant="download" onClick={exportList} disabled={saving} icon={<AdminIcon name="download" size={20} />}>一覧をダウンロード</Button>
          </>
        }
      />

      {error && <div className={styles.error} role="alert">{error}</div>}
      {loading ? <p className={styles.loading}>読み込み中...</p> : (
        <div className={styles.typeList}>
          {types.map((type) => {
            const labelEditing = editingLabel[type.id] !== undefined;
            const additions = addingRows[type.id] || [];
            return (
              <section className={styles.typeSection} key={type.id}>
                <TableFrame>
                  <Table>
                    <thead>
                      <TableRow>
                        <TableHeaderCell colSpan={2}>
                          <span className={styles.fixedName}>{type.fixed_name}：</span>
                          {labelEditing ? (
                            <FormField
                              compact
                              wrapperClassName={styles.labelField}
                              inputClassName={styles.labelInput}
                              value={editingLabel[type.id]}
                              maxLength={100}
                              aria-label={`${type.fixed_name}の種別ラベル`}
                              onChange={(event) => setEditingLabel((current) => ({ ...current, [type.id]: event.target.value }))}
                            />
                          ) : type.display_label}
                        </TableHeaderCell>
                        <TableHeaderCell className={styles.actionCell}>
                          <TableActions>
                            {labelEditing ? (
                              <>
                                <Button variant="text" icon={<AdminIcon name="edit" size={17} />} onClick={() => handleLabelSave(type.id)} disabled={saving}>更新</Button>
                                <Button variant="text" focusTone="danger" className={styles.dangerAction} onClick={() => cancelLabelEdit(type.id)} disabled={saving}>キャンセル</Button>
                              </>
                            ) : (
                              <Button variant="text" icon={<AdminIcon name="edit" size={17} />} onClick={() => setEditingLabel((current) => ({ ...current, [type.id]: type.display_label }))} disabled={saving}>編集</Button>
                            )}
                          </TableActions>
                        </TableHeaderCell>
                      </TableRow>
                    </thead>
                  </Table>

                  <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(event) => handleDragEnd(type.id, event)}>
                    <SortableContext items={type.values.map((value) => value.id)} strategy={verticalListSortingStrategy}>
                      <Table>
                        <tbody>
                          {type.values.map((value) => (
                            <SortableValueRow
                              key={value.id}
                              value={value}
                              editing={editingValue[value.id] !== undefined}
                              editingValue={editingValue[value.id] || ""}
                              saving={saving}
                              onEdit={() => setEditingValue((current) => ({ ...current, [value.id]: value.value_name }))}
                              onChange={(next) => setEditingValue((current) => ({ ...current, [value.id]: next }))}
                              onSave={() => saveValue(type.id, value.id, value.version)}
                              onCancel={() => cancelValueEdit(value.id)}
                              onDelete={() => {
                                setError(null);
                                setDeleteTarget({ typeId: type.id, valueId: value.id, valueName: value.value_name, version: value.version });
                              }}
                            />
                          ))}
                          {additions.map((value, index) => (
                            <TableRow className={styles.addingRow} key={`new-${index}`}>
                              <TableCell className={styles.handleCell} />
                              <TableCell className={styles.valueCell}>
                                <FormField
                                  compact
                                  wrapperClassName={styles.valueField}
                                  autoFocus
                                  inputClassName={styles.valueInput}
                                  value={value}
                                  maxLength={200}
                                  aria-label={`${type.fixed_name}の追加種別値`}
                                  onChange={(event) => changeAddRow(type.id, index, event.target.value)}
                                />
                              </TableCell>
                              <TableCell className={styles.actionCell}>
                                <TableActions>
                                  <Button variant="text" onClick={() => registerValue(type.id, index)} disabled={saving}>登録</Button>
                                  <Button variant="text" focusTone="danger" className={styles.dangerAction} onClick={() => cancelAddRow(type.id, index)} disabled={saving}>キャンセル</Button>
                                </TableActions>
                              </TableCell>
                            </TableRow>
                          ))}
                        </tbody>
                      </Table>
                    </SortableContext>
                  </DndContext>
                </TableFrame>
                <Button className={styles.addButton} variant="add" icon={<AdminIcon name="plus" size={21} />} onClick={() => addRow(type.id)} disabled={saving}>追加</Button>
              </section>
            );
          })}
        </div>
      )}

      <Modal
        open={Boolean(deleteTarget)}
        title={modalMessages.deleteValue.title}
        variant="danger"
        cancelLabel={modalMessages.deleteValue.cancel}
        confirmLabel={modalMessages.deleteValue.confirm}
        busy={saving}
        error={error}
        onConfirm={deleteValue}
        onClose={() => setDeleteTarget(null)}
      >
        {modalMessages.deleteValue.body(deleteTarget?.valueName ?? "")}
      </Modal>
      <Modal
        open={Boolean(pendingNavigation)}
        title={modalMessages.discardChanges.title}
        cancelLabel={modalMessages.discardChanges.cancel}
        confirmLabel={modalMessages.discardChanges.confirm}
        busy={saving}
        onConfirm={() => {
          const path = pendingNavigation;
          setPendingNavigation(null);
          if (path) router.push(path);
        }}
        onClose={() => setPendingNavigation(null)}
      >
        {modalMessages.discardChanges.body}
      </Modal>
    </AdminLayout>
  );
}
