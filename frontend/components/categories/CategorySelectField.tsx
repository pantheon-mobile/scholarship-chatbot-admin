"use client";

import { SelectHTMLAttributes, useMemo } from "react";

import { SelectField } from "@/components/admin";
import { Category } from "@/types/category";

type CategorySelectFieldProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "children"> & {
  categories: Category[];
  label?: string;
  wrapperClassName?: string;
  emptyLabel?: string;
  error?: string;
};

function flattenCategories(categories: Category[]) {
  const children = new Map<number | null, Category[]>();
  for (const category of categories) {
    const siblings = children.get(category.parent_id) ?? [];
    siblings.push(category);
    children.set(category.parent_id, siblings);
  }
  for (const siblings of children.values()) {
    siblings.sort((left, right) => left.display_order - right.display_order || left.id - right.id);
  }
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

export function CategorySelectField({ categories, emptyLabel = "未選択", ...props }: CategorySelectFieldProps) {
  const options = useMemo(() => flattenCategories(categories), [categories]);
  return <SelectField {...props}>
    <option value="">{emptyLabel}</option>
    {options.map(({ category, depth }) => (
      <option key={category.id} value={category.id}>{`${"　".repeat(depth)}${category.name}`}</option>
    ))}
  </SelectField>;
}
