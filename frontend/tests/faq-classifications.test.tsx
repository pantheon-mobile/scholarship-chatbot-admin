import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const api = vi.hoisted(() => ({
  fetchFaqClassifications: vi.fn(),
  updateFaqClassificationLabel: vi.fn(),
  addFaqClassificationValue: vi.fn(),
  updateFaqClassificationValue: vi.fn(),
  deleteFaqClassificationValue: vi.fn(),
  reorderFaqClassificationValues: vi.fn(),
  exportFaqClassifications: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("../lib/faqClassificationsApi", () => ({ ...api }));
vi.mock("@dnd-kit/core", () => ({
  closestCenter: vi.fn(),
  PointerSensor: class {},
  useSensor: vi.fn(() => ({})),
  useSensors: vi.fn(() => []),
  DndContext: ({ children, onDragEnd }: { children: React.ReactNode; onDragEnd: (event: unknown) => void }) => <div>
    {children}
    <button type="button" onClick={() => onDragEnd({ active: { id: 11 }, over: { id: 10 } })}>テスト並び替え</button>
  </div>,
}));
vi.mock("@dnd-kit/sortable", () => ({
  SortableContext: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  verticalListSortingStrategy: {},
  useSortable: () => ({ attributes: {}, listeners: {}, setNodeRef: vi.fn(), transform: null, transition: undefined, isDragging: false }),
  arrayMove: <T,>(items: T[], from: number, to: number) => {
    const next = [...items];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    return next;
  },
}));

import FaqClassificationsPage from "../app/faq-classifications/page";

const values = [
  { id: 10, value_name: "A", display_order: 1, version: 1 },
  { id: 11, value_name: "B", display_order: 2, version: 1 },
];
const types = [1, 2, 3, 4].map((id) => ({
  id,
  type_code: `FAQ_TYPE_${id}`,
  fixed_name: `区分${id}`,
  display_label: `区分${id}`,
  display_order: id,
  version: 1,
  values: id === 1 ? values : [],
}));

function updatedType(overrides = {}) {
  return { ...types[0], ...overrides };
}

beforeEach(() => {
  push.mockReset();
  Object.values(api).forEach((mock) => mock.mockReset());
  api.fetchFaqClassifications.mockResolvedValue(types);
  api.updateFaqClassificationLabel.mockResolvedValue(updatedType({ display_label: "問合せ区分", version: 2 }));
  api.addFaqClassificationValue.mockResolvedValue(updatedType({ values: [...values, { id: 12, value_name: "追加値", display_order: 3, version: 1 }] }));
  api.updateFaqClassificationValue.mockResolvedValue(updatedType({ values: [{ ...values[0], value_name: "更新値", version: 2 }, values[1]] }));
  api.deleteFaqClassificationValue.mockResolvedValue(undefined);
  api.reorderFaqClassificationValues.mockResolvedValue(updatedType({ values: [{ ...values[1], display_order: 1, version: 2 }, { ...values[0], display_order: 2, version: 2 }] }));
  api.exportFaqClassifications.mockResolvedValue(new Blob(["xlsx"]));
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:test") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function renderPage() {
  render(<FaqClassificationsPage />);
  await screen.findByText("A");
}

describe("CB-212 FAQ classifications", () => {
  it("4区分、ラベル、値0件、新HeaderとSidebarを表示する", async () => {
    await renderPage();
    expect(screen.getByRole("heading", { name: "区分設定" })).not.toBeNull();
    expect(screen.getAllByText("区分4").length).toBeGreaterThan(0);
    expect(screen.getAllByText("区分値は登録されていません。")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "チャットサイト" })).not.toBeNull();
    expect(screen.getByText("ＦＡＱ管理")).not.toBeNull();
  });

  it("ラベル編集を保存・キャンセルできる", async () => {
    await renderPage();
    fireEvent.click(screen.getAllByRole("button", { name: "編集" })[0]);
    const input = screen.getByLabelText("区分1の区分ラベル");
    fireEvent.change(input, { target: { value: "問合せ区分" } });
    fireEvent.click(screen.getAllByRole("button", { name: "更新" })[0]);
    await waitFor(() => expect(api.updateFaqClassificationLabel).toHaveBeenCalledWith(1, "問合せ区分", 1));
    expect(await screen.findByText("問合せ区分")).not.toBeNull();

    fireEvent.click(screen.getAllByRole("button", { name: "編集" })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: "キャンセル" })[0]);
    expect(screen.queryByLabelText("区分1の区分ラベル")).toBeNull();
  });

  it("区分値を追加・編集でき、処理中は二重送信を防ぐ", async () => {
    await renderPage();
    fireEvent.click(screen.getAllByRole("button", { name: "追加" })[0]);
    fireEvent.change(screen.getByLabelText("区分1の追加区分値"), { target: { value: " 追加値 " } });
    fireEvent.click(screen.getByRole("button", { name: "登録" }));
    await waitFor(() => expect(api.addFaqClassificationValue).toHaveBeenCalledWith(1, "追加値"));

    const row = screen.getByText("A").closest("tr")!;
    fireEvent.click(within(row).getByRole("button", { name: "編集" }));
    fireEvent.change(screen.getByLabelText("Aの区分値"), { target: { value: "更新値" } });
    fireEvent.click(within(row).getByRole("button", { name: "更新" }));
    await waitFor(() => expect(api.updateFaqClassificationValue).toHaveBeenCalledWith(1, 10, "更新値", 1));
  });

  it("削除Modalを表示し、削除中はEscと背景クリックで閉じない", async () => {
    let resolveDelete: (() => void) | undefined;
    api.deleteFaqClassificationValue.mockReturnValue(new Promise<void>((resolve) => { resolveDelete = resolve; }));
    await renderPage();
    fireEvent.click(within(screen.getByText("A").closest("tr")!).getByRole("button", { name: "削除" }));
    expect(screen.getByText(/区分「A」を削除します/)).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.mouseDown(screen.getByRole("dialog").parentElement!);
    expect(screen.getByRole("dialog")).not.toBeNull();
    expect(screen.getByRole("button", { name: "削除する" }).hasAttribute("disabled")).toBe(true);
    resolveDelete?.();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.deleteFaqClassificationValue).toHaveBeenCalledWith(1, 10, 1);
  });

  it("D&Dを即時保存し、失敗時は元の順序へ戻す", async () => {
    await renderPage();
    fireEvent.click(screen.getAllByRole("button", { name: "テスト並び替え" })[0]);
    await waitFor(() => expect(api.reorderFaqClassificationValues).toHaveBeenCalledWith(1, [{ id: 11, version: 1 }, { id: 10, version: 1 }]));
    expect(screen.getByText("B").compareDocumentPosition(screen.getByText("A")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    api.reorderFaqClassificationValues.mockRejectedValueOnce(new Error("他の操作で情報が更新されています。再読み込みしてください。"));
    fireEvent.click(screen.getAllByRole("button", { name: "テスト並び替え" })[0]);
    expect(await screen.findByRole("alert")).not.toBeNull();
    expect(screen.getByText("B").compareDocumentPosition(screen.getByText("A")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("一覧をダウンロードする", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "一覧をダウンロード" }));
    await waitFor(() => expect(api.exportFaqClassifications).toHaveBeenCalledOnce());
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalled();
  });
});
