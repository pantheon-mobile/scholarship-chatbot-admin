import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CategorySelectField } from "@/components/categories/CategorySelectField";

afterEach(cleanup);

const categories = [
  { id: 2, name: "第二ルート", parent_id: null, display_order: 2, version: 1, has_children: false, created_at: "", updated_at: "" },
  { id: 4, name: "孫", parent_id: 3, display_order: 1, version: 1, has_children: false, created_at: "", updated_at: "" },
  { id: 3, name: "子", parent_id: 1, display_order: 1, version: 1, has_children: true, created_at: "", updated_at: "" },
  { id: 1, name: "第一ルート", parent_id: null, display_order: 1, version: 1, has_children: true, created_at: "", updated_at: "" },
];

describe("CategorySelectField", () => {
  it("display_orderに従う任意階層と未選択を表示し、全階層を選択できる", () => {
    const onChange = vi.fn();
    render(<CategorySelectField aria-label="カテゴリ" categories={categories} value="" onChange={onChange} />);
    const select = screen.getByLabelText("カテゴリ") as HTMLSelectElement;
    expect(Array.from(select.options).map((option) => option.text)).toEqual([
      "未選択", "第一ルート", "　子", "　　孫", "第二ルート",
    ]);
    fireEvent.change(select, { target: { value: "1" } });
    fireEvent.change(select, { target: { value: "3" } });
    fireEvent.change(select, { target: { value: "4" } });
    expect(onChange).toHaveBeenCalledTimes(3);
  });
});
