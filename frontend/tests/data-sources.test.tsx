import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DataSourcesPage from "../app/data-sources/page";
import { DataSourcesApiError } from "../types/dataSource";

const push = vi.fn();
const api = vi.hoisted(() => ({
  fetchDataSources: vi.fn(), updateAnswerSource: vi.fn(), updateReferenceLink: vi.fn(),
  deleteDataSource: vi.fn(), bulkDeleteDataSources: vi.fn(), exportDataSources: vi.fn(),
  fetchDataSourceTypes: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("../lib/dataSourcesApi", () => ({ ...api }));
vi.mock("../lib/api", () => ({ fetchDataSourceTypes: api.fetchDataSourceTypes }));

const rows = [
  {
    id: 1, source_type: "FILE", title: "募集要項", format: "pdf", status: "AVAILABLE",
    category_name: null, size_bytes: 1024, character_count: 2000, answer_source_enabled: true,
    priority: "HIGH", reference_link_visible: true, updated_at: "2026-08-06T01:00:00Z", version: 1,
    file: { file_name: "guide.pdf" }, website: null,
    classifications: [{ type_code: "TYPE_1", classification_type_id: 1, classification_value_id: 1, display_label: "種別1", value_name: "在学生" }],
  },
  {
    id: 2, source_type: "WEB", title: "大学サイト", format: "Web", status: "TRAINING",
    category_name: null, size_bytes: null, character_count: 3000, answer_source_enabled: false,
    priority: "LOW", reference_link_visible: false, updated_at: "2026-08-05T01:00:00Z", version: 3,
    file: null, website: { url: "https://example.com", last_fetched_at: null }, classifications: [],
  },
] as const;

const response = { items: rows, page: 1, page_size: 10, total_count: 12, total_pages: 2, total_size_bytes: 1024, sort: "updated_at", order: "desc" };
const types = [{ id: 1, type_code: "TYPE_1", fixed_name: "種別1", display_label: "対象者", display_order: 1, version: 1, values: [{ id: 1, value_name: "在学生", display_order: 1, version: 1 }] }];

beforeEach(() => {
  push.mockReset();
  Object.values(api).forEach((mock) => mock.mockReset());
  api.fetchDataSources.mockResolvedValue(response);
  api.fetchDataSourceTypes.mockResolvedValue(types);
  api.updateAnswerSource.mockResolvedValue({ ...rows[0], answer_source_enabled: false, version: 2 });
  api.updateReferenceLink.mockResolvedValue({ ...rows[0], reference_link_visible: false, version: 2 });
  api.deleteDataSource.mockResolvedValue(undefined);
  api.bulkDeleteDataSources.mockResolvedValue(2);
  api.exportDataSources.mockResolvedValue(new Blob(["xlsx"]));
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:test") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function renderPage() {
  render(<DataSourcesPage />);
  await screen.findByText("募集要項");
}

describe("CB-202 data sources", () => {
  it("初期表示を更新日時降順・10件で取得する", async () => {
    await renderPage();
    expect(screen.getByText("データソース数 12件")).not.toBeNull();
    expect(api.fetchDataSources).toHaveBeenCalledWith(expect.objectContaining({ sort: "updated_at", order: "desc", page_size: 10 }));
  });

  it("検索条件を適用する", async () => {
    await renderPage();
    fireEvent.change(screen.getByPlaceholderText("キーワードを入力"), { target: { value: "奨学金" } });
    fireEvent.click(screen.getByRole("button", { name: "絞り込み検索" }));
    await waitFor(() => expect(api.fetchDataSources).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: "奨学金", page: 1 })));
  });

  it("IDをソートし、表示件数とページを変更する", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: /IDを昇順/ }));
    await waitFor(() => expect(api.fetchDataSources).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "id", order: "asc" })));
    fireEvent.change(screen.getByLabelText("表示件数"), { target: { value: "20" } });
    await waitFor(() => expect(api.fetchDataSources).toHaveBeenLastCalledWith(expect.objectContaining({ page_size: 20 })));
    fireEvent.click(screen.getByRole("button", { name: "次へ" }));
    await waitFor(() => expect(api.fetchDataSources).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("全選択・全解除とindeterminateを管理する", async () => {
    await renderPage();
    const rowOne = screen.getByLabelText("募集要項を選択");
    fireEvent.click(rowOne);
    const selectors = screen.getAllByLabelText("表示中ページを全選択") as HTMLInputElement[];
    expect(selectors[0].indeterminate).toBe(true);
    fireEvent.click(selectors[0]);
    expect(screen.getByLabelText("募集要項を選択").getAttribute("checked")).toBeNull();
    expect((screen.getByLabelText("大学サイトを選択") as HTMLInputElement).checked).toBe(true);
    fireEvent.click(selectors[0]);
    expect((screen.getByLabelText("大学サイトを選択") as HTMLInputElement).checked).toBe(false);
  });

  it("トグル成功時は返却versionを保持する", async () => {
    await renderPage();
    fireEvent.click(screen.getAllByRole("switch")[0]);
    await waitFor(() => expect(api.updateAnswerSource).toHaveBeenCalledWith(1, false, 1));
    fireEvent.click(screen.getAllByRole("switch")[0]);
    await waitFor(() => expect(api.updateAnswerSource).toHaveBeenLastCalledWith(1, true, 2));
  });

  it("トグル失敗時は元の表示へ戻してエラーを出す", async () => {
    api.updateAnswerSource.mockRejectedValueOnce(new Error("更新失敗"));
    await renderPage();
    const toggle = screen.getAllByRole("switch")[0];
    fireEvent.click(toggle);
    await screen.findByRole("alert");
    expect(toggle.getAttribute("aria-checked")).toBe("true");
  });

  it("行削除Modalから削除する", async () => {
    await renderPage();
    fireEvent.click(screen.getAllByRole("button", { name: "削除" }).at(-1)!);
    expect(screen.getByRole("dialog")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));
    await waitFor(() => expect(api.deleteDataSource).toHaveBeenCalledWith(2, 3));
  });

  it("選択行を一括削除する", async () => {
    await renderPage();
    fireEvent.click(screen.getAllByLabelText("表示中ページを全選択")[0]);
    fireEvent.click(screen.getAllByRole("button", { name: "削除" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));
    await waitFor(() => expect(api.bulkDeleteDataSources).toHaveBeenCalledWith([{ id: 1, version: 1 }, { id: 2, version: 3 }]));
  });

  it("PAGE_NOT_FOUNDだけ共通Modalを表示する", async () => {
    api.fetchDataSources.mockRejectedValueOnce(new DataSourcesApiError("ページがありません。", 422, "PAGE_NOT_FOUND"));
    render(<DataSourcesPage />);
    expect(await screen.findByRole("dialog")).not.toBeNull();
    expect(screen.getByText("指定されたページは存在しません。")).not.toBeNull();
  });

  it("直接指定した範囲外ページはAPIのPAGE_NOT_FOUNDを受けてModalを表示する", async () => {
    await renderPage();
    api.fetchDataSources.mockRejectedValueOnce(new DataSourcesApiError("ページがありません。", 422, "PAGE_NOT_FOUND"));
    const pageInput = screen.getByLabelText("ページ番号");
    fireEvent.change(pageInput, { target: { value: "99" } });
    fireEvent.submit(pageInput.closest("form")!);
    expect(await screen.findByRole("dialog")).not.toBeNull();
    expect(api.fetchDataSources).toHaveBeenLastCalledWith(expect.objectContaining({ page: 99 }));
  });

  it("Excel出力と種別設定への遷移を実行する", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "一覧をダウンロード" }));
    await waitFor(() => expect(api.exportDataSources).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "種別を設定する" }));
    expect(push).toHaveBeenCalledWith("/data-source-types");
  });
});
