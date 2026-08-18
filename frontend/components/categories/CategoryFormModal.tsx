"use client";

import { useEffect, useMemo, useState } from "react";

import { FormField, Modal, SelectField } from "@/components/admin";
import { Category } from "@/types/category";
import styles from "./category-form-modal.module.css";

export type CategoryFormValues = { name: string; parent_id: number | null };

type CategoryFormModalProps = {
  open: boolean;
  mode: "create" | "edit";
  categories: Category[];
  category?: Category;
  busy?: boolean;
  error?: string;
  errorCode?: string;
  onSubmit: (values: CategoryFormValues) => void;
  onClose: () => void;
};

function descendantIds(categoryId: number, categories: Category[]) {
  const result = new Set<number>();
  const stack = [categoryId];
  while (stack.length) {
    const current = stack.pop()!;
    for (const child of categories.filter((item) => item.parent_id === current)) {
      if (!result.has(child.id)) {
        result.add(child.id);
        stack.push(child.id);
      }
    }
  }
  return result;
}

function hierarchyOptions(categories: Category[], excluded: Set<number>) {
  const children = new Map<number | null, Category[]>();
  for (const category of categories) {
    if (excluded.has(category.id)) continue;
    const siblings = children.get(category.parent_id) ?? [];
    siblings.push(category);
    children.set(category.parent_id, siblings);
  }
  for (const siblings of children.values()) siblings.sort((a, b) => a.display_order - b.display_order || a.id - b.id);
  const result: Array<{ category: Category; depth: number }> = [];
  const visit = (parentId: number | null, depth: number) => {
    for (const category of children.get(parentId) ?? []) {
      result.push({ category, depth });
      visit(category.id, depth + 1);
    }
  };
  visit(null, 0);
  return result;
}

export function CategoryFormModal({ open, mode, categories, category, busy = false, error, errorCode, onSubmit, onClose }: CategoryFormModalProps) {
  const initialName = mode === "edit" ? category?.name ?? "" : "";
  const initialParentId = mode === "edit" ? category?.parent_id ?? null : null;
  const [name, setName] = useState(initialName);
  const [parentId, setParentId] = useState<number | null>(initialParentId);
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    if (!open) return;
    setName(initialName);
    setParentId(initialParentId);
    setLocalError("");
  }, [open, initialName, initialParentId]);

  const excluded = useMemo(() => {
    if (mode !== "edit" || !category) return new Set<number>();
    return new Set([category.id, ...descendantIds(category.id, categories)]);
  }, [mode, category, categories]);
  const options = useMemo(() => hierarchyOptions(categories, excluded), [categories, excluded]);
  const normalizedName = name.trim();
  const dirty = mode === "create"
    ? normalizedName.length > 0 || parentId !== null
    : normalizedName !== initialName || parentId !== initialParentId;
  const nameError = localError || (["CATEGORY_NAME_REQUIRED", "CATEGORY_NAME_TOO_LONG", "CATEGORY_NAME_DUPLICATE"].includes(errorCode ?? "") ? error : undefined);
  const parentError = errorCode === "PARENT_CATEGORY_NOT_FOUND" || errorCode === "CATEGORY_CYCLE_NOT_ALLOWED" ? error : undefined;
  const modalError = nameError || parentError ? undefined : error;

  const submit = () => {
    if (!normalizedName) {
      setLocalError("カテゴリが入力されていません");
      return;
    }
    if (normalizedName.length > 15) {
      setLocalError("カテゴリは15文字以内で入力してください。");
      return;
    }
    setLocalError("");
    onSubmit({ name: normalizedName, parent_id: parentId });
  };

  return <Modal
    open={open}
    title={mode === "create" ? "カテゴリ新規追加" : "カテゴリ編集"}
    confirmLabel={busy ? (mode === "create" ? "登録中..." : "更新中...") : mode === "create" ? "カテゴリ登録" : "カテゴリ更新"}
    busy={busy}
    confirmDisabled={!normalizedName || normalizedName.length > 15 || (mode === "edit" && !dirty)}
    error={modalError}
    onConfirm={submit}
    onClose={onClose}
  >
    <div className={styles.form}>
      <FormField
        id={`${mode}-category-name`}
        label="カテゴリ名"
        value={name}
        error={nameError}
        aria-required="true"
        autoComplete="off"
        onChange={(event) => { setName(event.target.value); setLocalError(""); }}
      />
      <SelectField id={`${mode}-parent-category`} label="親カテゴリ" value={parentId ?? ""} error={parentError} onChange={(event) => setParentId(event.target.value ? Number(event.target.value) : null)}>
        <option value="">親カテゴリを選択（第一階層）</option>
        {options.map(({ category: option, depth }) => <option key={option.id} value={option.id}>{`${"　".repeat(depth)}${option.name}`}</option>)}
      </SelectField>
    </div>
  </Modal>;
}
