"use client";

import { useEffect, useMemo, useState } from "react";
import { DndContext, DragEndEvent, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { arrayMove, SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useRouter } from "next/navigation";

import { AdminIcon, AdminLayout, Button, Checkbox, Modal, PageHeader, Table, TableCell, TableFrame, TableHeaderCell, TableRow } from "@/components/admin";
import { CategoryFormModal, CategoryFormValues } from "@/components/categories/CategoryFormModal";
import { bulkDeleteCategories, createCategory, deleteCategory, exportCategories, fetchCategories, reorderCategories, updateCategory } from "@/lib/categoriesApi";
import { Category, CategoryApiError } from "@/types/category";
import styles from "./page.module.css";

type VisibleCategory = Category & { depth: number };
type DeleteState = { kind: "single"; category: Category } | { kind: "bulk"; categories: Category[] } | null;
type FormState = { mode: "create" } | { mode: "edit"; category: Category } | null;

function childrenByParent(categories: Category[]) {
  const result = new Map<number | null, Category[]>();
  for (const category of categories) {
    const siblings = result.get(category.parent_id) ?? [];
    siblings.push(category);
    result.set(category.parent_id, siblings);
  }
  for (const siblings of result.values()) siblings.sort((a, b) => a.display_order - b.display_order || a.id - b.id);
  return result;
}

function visibleCategories(categories: Category[], expanded: Set<number>): VisibleCategory[] {
  const children = childrenByParent(categories);
  const result: VisibleCategory[] = [];
  const visit = (parentId: number | null, depth: number) => {
    for (const category of children.get(parentId) ?? []) {
      result.push({ ...category, depth });
      if (expanded.has(category.id)) visit(category.id, depth + 1);
    }
  };
  visit(null, 0);
  return result;
}

function SortableCategoryRow({ category, selected, expanded, onSelect, onToggle, onEdit, onDelete }: {
  category: VisibleCategory;
  selected: boolean;
  expanded: boolean;
  onSelect: (checked: boolean) => void;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: category.id });
  return <TableRow ref={setNodeRef} className={isDragging ? styles.draggingRow : ""} style={{ transform: CSS.Transform.toString(transform), transition }}>
    <TableCell className={styles.handleCell}>
      <button type="button" className={styles.dragHandle} aria-label={`${category.name}を並び替え`} {...attributes} {...listeners}>
        <AdminIcon name="grip" size={24} />
      </button>
    </TableCell>
    <TableCell className={styles.checkCell}><Checkbox aria-label={`${category.name}を選択`} checked={selected} onChange={(event) => onSelect(event.target.checked)} /></TableCell>
    <TableCell>
      <div className={styles.categoryName} style={{ paddingLeft: category.depth * 40 }}>
        {category.has_children ? <button type="button" className={styles.disclosure} aria-label={`${category.name}を${expanded ? "折り畳む" : "展開する"}`} aria-expanded={expanded} onClick={onToggle}>
          <AdminIcon name={expanded ? "chevronDown" : "chevronRight"} size={21} />
        </button> : <span className={styles.disclosureSpacer} />}
        <span>{category.name}</span>
      </div>
    </TableCell>
    <TableCell className={styles.idCell}>ID:{category.id}</TableCell>
    <TableCell className={styles.actionCell}><Button variant="text" icon={<AdminIcon name="edit" size={17} />} onClick={onEdit}>編集</Button></TableCell>
    <TableCell className={styles.actionCell}><Button variant="text" focusTone="danger" icon={<AdminIcon name="trash" size={17} />} onClick={onDelete}>削除</Button></TableCell>
  </TableRow>;
}

export default function CategoriesPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<Category[]>([]);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleteState, setDeleteState] = useState<DeleteState>(null);
  const [formState, setFormState] = useState<FormState>(null);
  const [formError, setFormError] = useState("");
  const [formErrorCode, setFormErrorCode] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetchCategories();
      setCategories(response.items);
      setExpanded(new Set(response.items.filter((item) => item.has_children).map((item) => item.id)));
      setSelected(new Set());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "カテゴリ一覧の取得に失敗しました。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const visible = useMemo(() => visibleCategories(categories, expanded), [categories, expanded]);
  const selectedRows = categories.filter((category) => selected.has(category.id));
  const allSelected = categories.length > 0 && selected.size === categories.length;
  const someSelected = selected.size > 0 && !allSelected;

  const toggleAll = (checked: boolean) => setSelected(checked ? new Set(categories.map((category) => category.id)) : new Set());

  const saveCategory = async (values: CategoryFormValues) => {
    if (!formState) return;
    setBusy(true);
    setFormError("");
    setFormErrorCode(undefined);
    try {
      const saved = formState.mode === "create"
        ? await createCategory(values)
        : await updateCategory(formState.category.id, { ...values, version: formState.category.version });
      setFormState(null);
      await load();
      if (saved.parent_id !== null) setExpanded((current) => new Set(current).add(saved.parent_id!));
    } catch (reason) {
      const conflict = reason instanceof CategoryApiError && reason.code === "CATEGORY_VERSION_CONFLICT";
      setFormError(conflict ? "他の操作で情報が更新されています。再読み込みしてください。" : reason instanceof Error ? reason.message : "カテゴリの保存に失敗しました。");
      setFormErrorCode(reason instanceof CategoryApiError ? reason.code : undefined);
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteState) return;
    setBusy(true);
    setError("");
    try {
      if (deleteState.kind === "single") await deleteCategory(deleteState.category.id, deleteState.category.version);
      else await bulkDeleteCategories(deleteState.categories.map(({ id, version }) => ({ id, version })));
      setDeleteState(null);
      await load();
    } catch (reason) {
      const message = reason instanceof CategoryApiError && reason.code === "CATEGORY_VERSION_CONFLICT"
        ? "他の操作で情報が更新されています。再読み込みしてください。"
        : reason instanceof Error ? reason.message : "カテゴリの削除に失敗しました。";
      setError(message);
    } finally {
      setBusy(false);
    }
  };

  const onDragEnd = async ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    const activeCategory = categories.find((category) => category.id === active.id);
    const overCategory = categories.find((category) => category.id === over.id);
    if (!activeCategory || !overCategory) return;
    if (activeCategory.parent_id !== overCategory.parent_id) {
      setError("異なる親カテゴリ間では並び替えできません。");
      return;
    }
    const parentId = activeCategory.parent_id;
    const siblings = (childrenByParent(categories).get(parentId) ?? []);
    const oldIndex = siblings.findIndex((category) => category.id === activeCategory.id);
    const newIndex = siblings.findIndex((category) => category.id === overCategory.id);
    const reordered = arrayMove(siblings, oldIndex, newIndex).map((category, index) => ({ ...category, display_order: index + 1 }));
    const previous = categories;
    const reorderedById = new Map(reordered.map((category) => [category.id, category]));
    setCategories(categories.map((category) => reorderedById.get(category.id) ?? category));
    setError("");
    try {
      const updated = await reorderCategories(parentId, reordered.map(({ id, version }) => ({ id, version })));
      const updatedById = new Map(updated.map((category) => [category.id, category]));
      setCategories((current) => current.map((category) => updatedById.get(category.id) ?? category));
    } catch (reason) {
      setCategories(previous);
      setError(reason instanceof CategoryApiError && reason.code === "CATEGORY_VERSION_CONFLICT"
        ? "他の操作で情報が更新されています。再読み込みしてください。"
        : reason instanceof Error ? reason.message : "カテゴリの並び替えに失敗しました。");
    }
  };

  const download = async () => {
    setError("");
    try {
      const { blob, fileName } = await exportCategories();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = fileName;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "カテゴリ一覧のダウンロードに失敗しました。");
    }
  };

  const modalBody = deleteState?.kind === "single"
    ? <>カテゴリ「{deleteState.category.name}」{deleteState.category.has_children ? "に含まれる全てのカテゴリ" : ""}を削除します。よろしいですか。<br />この操作は元に戻せません。</>
    : deleteState ? <>選択した{deleteState.categories.length}件のカテゴリを削除します。子カテゴリが含まれる場合は、その配下のカテゴリも削除されます。<br />この操作は元に戻せません。</> : null;

  return <AdminLayout activeMenu="categories" contentWidth="wide" contentAlign="start" onNavigate={(href) => router.push(href)}>
    <PageHeader title="カテゴリ一覧" />
    <div className={styles.toolbar}>
      <Button variant="primary" icon={<AdminIcon name="plus" size={20} />} onClick={() => { setFormError(""); setFormErrorCode(undefined); setFormState({ mode: "create" }); }}>カテゴリ追加</Button>
    </div>
    <div className={styles.listActions}>
      <div className={styles.bulkAction}>
        <Checkbox aria-label="全カテゴリを選択" checked={allSelected} indeterminate={someSelected} onChange={(event) => toggleAll(event.target.checked)} />
        <span>選択したカテゴリを</span>
        <Button variant="danger" icon={<AdminIcon name="trash" size={18} />} disabled={!selectedRows.length || busy} onClick={() => setDeleteState({ kind: "bulk", categories: selectedRows })}>削除</Button>
      </div>
      <Button variant="download" icon={<AdminIcon name="download" size={20} />} onClick={download}>一覧をダウンロード</Button>
    </div>
    {error && !deleteState && <div className={styles.error} role="alert">{error}</div>}
    <TableFrame>
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <Table>
          <colgroup><col className={styles.handleColumn} /><col className={styles.checkColumn} /><col /><col className={styles.idColumn} /><col className={styles.actionColumn} /><col className={styles.actionColumn} /></colgroup>
          <thead><TableRow><TableHeaderCell colSpan={6}>カテゴリ</TableHeaderCell></TableRow></thead>
          <SortableContext items={visible.map((category) => category.id)} strategy={verticalListSortingStrategy}>
            <tbody>
              {visible.map((category) => <SortableCategoryRow key={category.id} category={category} selected={selected.has(category.id)} expanded={expanded.has(category.id)}
                onSelect={(checked) => setSelected((current) => { const next = new Set(current); checked ? next.add(category.id) : next.delete(category.id); return next; })}
                onToggle={() => setExpanded((current) => { const next = new Set(current); next.has(category.id) ? next.delete(category.id) : next.add(category.id); return next; })}
                onEdit={() => { setFormError(""); setFormErrorCode(undefined); setFormState({ mode: "edit", category }); }} onDelete={() => setDeleteState({ kind: "single", category })} />)}
              {!loading && !visible.length && <TableRow><TableCell colSpan={6} className={styles.empty}>カテゴリは登録されていません。</TableCell></TableRow>}
              {loading && <TableRow><TableCell colSpan={6} className={styles.empty}>読み込み中...</TableCell></TableRow>}
            </tbody>
          </SortableContext>
        </Table>
      </DndContext>
    </TableFrame>
    <Modal open={Boolean(deleteState)} title={deleteState?.kind === "bulk" ? "カテゴリの一括削除" : "カテゴリの削除"} variant="danger" confirmLabel={busy ? "削除中..." : "削除する"} busy={busy} error={error || undefined} onConfirm={confirmDelete} onClose={() => { if (!busy) { setDeleteState(null); setError(""); } }}>
      <p className={styles.modalText}>{modalBody}</p>
    </Modal>
    <CategoryFormModal
      open={Boolean(formState)}
      mode={formState?.mode ?? "create"}
      category={formState?.mode === "edit" ? formState.category : undefined}
      categories={categories}
      busy={busy}
      error={formError || undefined}
      errorCode={formErrorCode}
      onSubmit={saveCategory}
      onClose={() => { if (!busy) { setFormState(null); setFormError(""); setFormErrorCode(undefined); } }}
    />
  </AdminLayout>;
}
