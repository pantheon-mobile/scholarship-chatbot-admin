import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CategoriesPage from "../app/categories/page";
import { CategoryApiError } from "../types/category";

const push = vi.fn();
const api = vi.hoisted(() => ({
  fetchCategories: vi.fn(),
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
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
  api.createCategory.mockResolvedValue({ ...categories[3], id: 6, name: "国内", parent_id: 2, display_order: 1, version: 1, has_children: false });
  api.updateCategory.mockResolvedValue({ ...categories[2], name: "継続申請", version: 2 });
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
    fireEvent.click(screen.getAllByRole("button", { name: /^削除$/ })[0]);
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
    fireEvent.click(screen.getAllByRole("button", { name: /^削除$/ })[0]);
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

  it("Excel出力と追加・編集Modalを表示し、ページ遷移しない", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "一覧をダウンロード" }));
    await waitFor(() => expect(api.exportCategories).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "カテゴリ追加" }));
    expect(screen.getByRole("dialog", { name: "カテゴリ新規追加" })).not.toBeNull();
    expect(push).not.toHaveBeenCalledWith("/categories/new");
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    const row = screen.getByText("給付").closest("tr")!;
    fireEvent.click(row.querySelectorAll("button")[1]);
    expect(screen.getByRole("dialog", { name: "カテゴリ編集" })).not.toBeNull();
    expect(push).not.toHaveBeenCalledWith("/categories/2/edit");
  });

  it("新規Modalで階層付き親候補を選び、trimした名称を登録する", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "カテゴリ追加" }));
    const register = screen.getByRole("button", { name: "カテゴリ登録" }) as HTMLButtonElement;
    expect(register.disabled).toBe(true);
    const options = Array.from((screen.getByLabelText("親カテゴリ") as HTMLSelectElement).options).map((option) => option.text);
    expect(options).toContain("　申請");
    expect(options).toContain("　　新規");
    fireEvent.change(screen.getByLabelText("カテゴリ名"), { target: { value: " 国内 " } });
    fireEvent.change(screen.getByLabelText("親カテゴリ"), { target: { value: "2" } });
    expect(register.disabled).toBe(false);
    fireEvent.click(register);
    await waitFor(() => expect(api.createCategory).toHaveBeenCalledWith({ name: "国内", parent_id: 2 }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.fetchCategories).toHaveBeenCalledTimes(2);
  });

  it("新規登録失敗時はModalと入力値を維持し、フィールドエラーを表示する", async () => {
    api.createCategory.mockRejectedValueOnce(new CategoryApiError("同じ親カテゴリ内に同名のカテゴリがあります。", 422, "CATEGORY_NAME_DUPLICATE"));
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "カテゴリ追加" }));
    fireEvent.change(screen.getByLabelText("カテゴリ名"), { target: { value: "申請" } });
    fireEvent.click(screen.getByRole("button", { name: "カテゴリ登録" }));
    expect(await screen.findByText("同じ親カテゴリ内に同名のカテゴリがあります。")).not.toBeNull();
    expect((screen.getByRole("textbox") as HTMLInputElement).value).toBe("申請");
    expect(screen.getByRole("dialog")).not.toBeNull();
  });

  it("編集Modalは現在値を表示し、自分自身と全子孫を親候補から除外する", async () => {
    await renderPage();
    const row = screen.getByText("全般").closest("tr")!;
    fireEvent.click(row.querySelectorAll("button")[2]);
    expect((screen.getByLabelText("カテゴリ名") as HTMLInputElement).value).toBe("全般");
    const select = screen.getByLabelText("親カテゴリ") as HTMLSelectElement;
    const values = Array.from(select.options).map((option) => option.value);
    expect(values).not.toContain("1");
    expect(values).not.toContain("3");
    expect(values).not.toContain("5");
    expect(values).toContain("2");
    expect((screen.getByRole("button", { name: "カテゴリ更新" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("編集のdirtyは実差分で判定し、元へ戻すと更新を無効化する", async () => {
    await renderPage();
    const row = screen.getByText("申請").closest("tr")!;
    fireEvent.click(row.querySelectorAll("button")[2]);
    const input = screen.getByLabelText("カテゴリ名");
    const update = screen.getByRole("button", { name: "カテゴリ更新" }) as HTMLButtonElement;
    fireEvent.change(input, { target: { value: "継続申請" } });
    expect(update.disabled).toBe(false);
    fireEvent.change(input, { target: { value: "申請" } });
    expect(update.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("親カテゴリ"), { target: { value: "2" } });
    expect(update.disabled).toBe(false);
    fireEvent.click(update);
    await waitFor(() => expect(api.updateCategory).toHaveBeenCalledWith(3, { name: "申請", parent_id: 2, version: 1 }));
  });

  it("編集version競合時は入力を保持してユーザー向けエラーを表示する", async () => {
    api.updateCategory.mockRejectedValueOnce(new CategoryApiError("競合", 409, "CATEGORY_VERSION_CONFLICT"));
    await renderPage();
    const row = screen.getByText("給付").closest("tr")!;
    fireEvent.click(row.querySelectorAll("button")[1]);
    fireEvent.change(screen.getByLabelText("カテゴリ名"), { target: { value: "給付制度" } });
    fireEvent.click(screen.getByRole("button", { name: "カテゴリ更新" }));
    expect(await screen.findByText("他の操作で情報が更新されています。再読み込みしてください。")).not.toBeNull();
    expect((screen.getByLabelText("カテゴリ名") as HTMLInputElement).value).toBe("給付制度");
  });

  it("処理中はEsc・背景クリック・二重送信を禁止する", async () => {
    let resolveCreate!: (value: unknown) => void;
    api.createCategory.mockReturnValueOnce(new Promise((resolve) => { resolveCreate = resolve; }));
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "カテゴリ追加" }));
    fireEvent.change(screen.getByLabelText("カテゴリ名"), { target: { value: "新カテゴリ" } });
    fireEvent.click(screen.getByRole("button", { name: "カテゴリ登録" }));
    await waitFor(() => expect((screen.getByRole("button", { name: "登録中..." }) as HTMLButtonElement).disabled).toBe(true));
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.mouseDown(screen.getByRole("dialog").parentElement!);
    expect(screen.getByRole("dialog")).not.toBeNull();
    expect(api.createCategory).toHaveBeenCalledTimes(1);
    await act(async () => { resolveCreate({ ...categories[0], id: 8, name: "新カテゴリ" }); });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("キャンセル・Esc・背景クリックで閉じ、起点へフォーカスを戻す", async () => {
    await renderPage();
    const trigger = screen.getByRole("button", { name: "カテゴリ追加" });
    trigger.focus();
    fireEvent.click(trigger);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "キャンセル" })));
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(trigger);
    fireEvent.click(trigger);
    fireEvent.mouseDown(screen.getByRole("dialog").parentElement!);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
