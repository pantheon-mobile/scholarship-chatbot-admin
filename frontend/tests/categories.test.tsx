import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CategoriesPage from "../app/categories/page";
import { CategoryApiError } from "../types/category";

const push = vi.fn();
const api = vi.hoisted(() => ({
  fetchCategories: vi.fn(),
  deleteCategory: vi.fn(),
  bulkDeleteCategories: vi.fn(),
  reorderCategories: vi.fn(),
  exportCategories: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("../lib/categoriesApi", () => ({ ...api }));
vi.mock("@dnd-kit/core", () => ({
  PointerSensor: function PointerSensor() {},
  useSensor: () => ({}),
  useSensors: () => [],
  DndContext: ({ children, onDragEnd }: { children: React.ReactNode; onDragEnd: (event: unknown) => void }) => <>
    <button type="button" onClick={() => onDragEnd({ active: { id: 4 }, over: { id: 3 } })}>同一親D&amp;D</button>
    <button type="button" onClick={() => onDragEnd({ active: { id: 3 }, over: { id: 2 } })}>別親D&amp;D</button>
    {children}
  </>,
}));
vi.mock("@dnd-kit/sortable", () => ({
  SortableContext: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  verticalListSortingStrategy: {},
  useSortable: () => ({ attributes: {}, listeners: {}, setNodeRef: vi.fn(), transform: null, transition: undefined, isDragging: false }),
  arrayMove: <T,>(items: T[], from: number, to: number) => {
    const result = [...items];
    const [item] = result.splice(from, 1);
    result.splice(to, 0, item);
    return result;
  },
}));
vi.mock("@dnd-kit/utilities", () => ({ CSS: { Transform: { toString: () => undefined } } }));

const categories = [
  { id: 1, name: "全般", parent_id: null, display_order: 1, version: 1, has_children: true, created_at: "2026-08-18T00:00:00Z", updated_at: "2026-08-18T00:00:00Z" },
  { id: 2, name: "給付", parent_id: null, display_order: 2, version: 1, has_children: false, created_at: "2026-08-18T00:00:00Z", updated_at: "2026-08-18T00:00:00Z" },
  { id: 3, name: "申請", parent_id: 1, display_order: 1, version: 1, has_children: true, created_at: "2026-08-18T00:00:00Z", updated_at: "2026-08-18T00:00:00Z" },
  { id: 4, name: "継続", parent_id: 1, display_order: 2, version: 1, has_children: false, created_at: "2026-08-18T00:00:00Z", updated_at: "2026-08-18T00:00:00Z" },
  { id: 5, name: "新規", parent_id: 3, display_order: 1, version: 1, has_children: false, created_at: "2026-08-18T00:00:00Z", updated_at: "2026-08-18T00:00:00Z" },
];

beforeEach(() => {
  push.mockReset();
  Object.values(api).forEach((mock) => mock.mockReset());
  api.fetchCategories.mockResolvedValue({ items: categories });
  api.deleteCategory.mockResolvedValue(undefined);
  api.bulkDeleteCategories.mockResolvedValue(5);
  api.reorderCategories.mockResolvedValue([
    { ...categories[3], display_order: 1, version: 2 },
    { ...categories[2], display_order: 2, version: 2 },
  ]);
  api.exportCategories.mockResolvedValue({ blob: new Blob(["xlsx"]), fileName: "category202608181200.xlsx" });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:category") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function renderPage() {
  render(<CategoriesPage />);
  await screen.findByText("新規");
}

describe("CB-213 categories", () => {
  it("初期表示は任意階層を全展開し、数値IDと新共通ヘッダを表示する", async () => {
    await renderPage();
    expect(screen.getByRole("heading", { name: "カテゴリ一覧" })).not.toBeNull();
    expect(screen.getByText("ID:5")).not.toBeNull();
    expect(screen.getByRole("button", { name: "チャットサイト" })).not.toBeNull();
    expect(screen.getByRole("button", { name: "サイドメニューを閉じる" })).not.toBeNull();
    expect(screen.getByLabelText("全般を折り畳む")).not.toBeNull();
    expect(screen.queryByLabelText("給付を折り畳む")).toBeNull();
  });

  it("空一覧を表示する", async () => {
    api.fetchCategories.mockResolvedValueOnce({ items: [] });
    render(<CategoriesPage />);
    expect(await screen.findByText("カテゴリは登録されていません。")).not.toBeNull();
  });

  it("展開・折り畳みを切り替える", async () => {
    await renderPage();
    fireEvent.click(screen.getByLabelText("全般を折り畳む"));
    expect(screen.queryByText("申請")).toBeNull();
    fireEvent.click(screen.getByLabelText("全般を展開する"));
    expect(screen.getByText("申請")).not.toBeNull();
  });

  it("全選択・全解除・indeterminateを管理し、折り畳み中の子も対象にする", async () => {
    await renderPage();
    fireEvent.click(screen.getByLabelText("全般を折り畳む"));
    fireEvent.click(screen.getByLabelText("全カテゴリを選択"));
    fireEvent.click(screen.getAllByRole("button", { name: "削除", exact: true })[0]);
    expect(screen.getByText(/選択した5件のカテゴリ/)).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    fireEvent.click(screen.getByLabelText("給付を選択"));
    expect((screen.getByLabelText("全カテゴリを選択") as HTMLInputElement).indeterminate).toBe(true);
    fireEvent.click(screen.getByLabelText("全カテゴリを選択"));
    expect((screen.getByLabelText("給付を選択") as HTMLInputElement).checked).toBe(true);
  });

  it("子あり個別削除Modalからversion付きで削除する", async () => {
    await renderPage();
    const row = screen.getByText("全般").closest("tr")!;
    fireEvent.click(row.querySelectorAll("button")[3]);
    expect(screen.getByText(/全てのカテゴリを削除します/)).not.toBeNull();
    expect(screen.getByText(/この操作は元に戻せません/)).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));
    await waitFor(() => expect(api.deleteCategory).toHaveBeenCalledWith(1, 1));
  });

  it("一括削除は明示選択したIDとversionを送る", async () => {
    await renderPage();
    fireEvent.click(screen.getByLabelText("全カテゴリを選択"));
    fireEvent.click(screen.getAllByRole("button", { name: "削除", exact: true })[0]);
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));
    await waitFor(() => expect(api.bulkDeleteCategories).toHaveBeenCalledWith(categories.map(({ id, version }) => ({ id, version }))));
  });

  it("削除失敗とversion競合を表示する", async () => {
    api.deleteCategory.mockRejectedValueOnce(new CategoryApiError("競合", 409, "CATEGORY_VERSION_CONFLICT"));
    await renderPage();
    const row = screen.getByText("給付").closest("tr")!;
    fireEvent.click(row.querySelectorAll("button")[2]);
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));
    expect(await screen.findByText("他の操作で情報が更新されています。再読み込みしてください。")).not.toBeNull();
  });

  it("同一親D&Dを即時保存し、失敗時は元の順番へ戻す", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "同一親D&D" }));
    await waitFor(() => expect(api.reorderCategories).toHaveBeenCalledWith(1, [{ id: 4, version: 1 }, { id: 3, version: 1 }]));
    api.reorderCategories.mockRejectedValueOnce(new Error("保存失敗"));
    fireEvent.click(screen.getByRole("button", { name: "同一親D&D" }));
    expect(await screen.findByText("保存失敗")).not.toBeNull();
  });

  it("異なる親へのD&DをAPI呼び出し前に拒否する", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "別親D&D" }));
    expect(screen.getByText("異なる親カテゴリ間では並び替えできません。")).not.toBeNull();
    expect(api.reorderCategories).not.toHaveBeenCalled();
  });

  it("Excel出力と追加・編集導線を実行する", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "一覧をダウンロード" }));
    await waitFor(() => expect(api.exportCategories).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "カテゴリ追加" }));
    expect(push).toHaveBeenCalledWith("/categories/new");
    const row = screen.getByText("給付").closest("tr")!;
    fireEvent.click(row.querySelectorAll("button")[1]);
    expect(push).toHaveBeenCalledWith("/categories/2/edit");
  });
});
