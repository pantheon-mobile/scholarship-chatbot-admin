import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DataSourceFileEditPage from "@/app/data-sources/[id]/file/edit/page";
import { DataSourcesApiError } from "@/types/dataSource";

const push = vi.fn();
const api = vi.hoisted(() => ({ fetchDataSource: vi.fn(), updateFileDataSource: vi.fn(), fetchDataSourceTypes: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }), useParams: () => ({ id: "1" }) }));
vi.mock("@/lib/dataSourcesApi", async () => {
  const actual = await vi.importActual<typeof import("@/lib/dataSourcesApi")>("@/lib/dataSourcesApi");
  return { ...actual, fetchDataSource: api.fetchDataSource, updateFileDataSource: api.updateFileDataSource };
});
vi.mock("@/lib/api", () => ({ fetchDataSourceTypes: api.fetchDataSourceTypes }));
vi.mock("@/lib/categoriesApi", () => ({ fetchCategories: vi.fn().mockResolvedValue({ items: [{ id: 7, name: "給付", parent_id: null, display_order: 1 }] }) }));

const types = [
  { id: 1, type_code: "TYPE_1", fixed_name: "種別1", display_label: "対象者", display_order: 1, version: 1, values: [{ id: 10, value_name: "在学生", display_order: 1, version: 1 }, { id: 11, value_name: "卒業生", display_order: 2, version: 1 }] },
  { id: 2, type_code: "TYPE_2", fixed_name: "種別2", display_label: "給付区分", display_order: 2, version: 1, values: [{ id: 20, value_name: "給付", display_order: 1, version: 1 }] },
  { id: 3, type_code: "TYPE_3", fixed_name: "種別3", display_label: "所属", display_order: 3, version: 1, values: [{ id: 30, value_name: "学部", display_order: 1, version: 1 }] },
];
const row = {
  id: 1, source_type: "FILE" as const, title: "募集要項", format: "pdf", status: "AVAILABLE" as const,
  category: { id: 7, name: "給付", parent_id: null, path: "給付" },
  category_name: "給付", size_bytes: 10 * 1024 * 1024 + 100, character_count: null,
  answer_source_enabled: true, priority: "MEDIUM" as const, reference_link_visible: true,
  updated_at: "2026-08-07T01:00:00Z", version: 2,
  file: { file_name: "guide.pdf" }, website: null,
  classifications: [{ type_code: "TYPE_1", classification_type_id: 1, classification_value_id: 10, display_label: "対象者", value_name: "在学生" }],
};

beforeEach(() => {
  push.mockReset();
  api.fetchDataSource.mockReset().mockResolvedValue(row);
  api.fetchDataSourceTypes.mockReset().mockResolvedValue(types);
  api.updateFileDataSource.mockReset().mockResolvedValue({ ...row, title: "更新後", version: 3 });
});
afterEach(cleanup);

async function renderLoaded() {
  render(<DataSourceFileEditPage />);
  await screen.findByDisplayValue("募集要項");
}

describe("CB-204 file edit page", () => {
  it("DB値とファイル情報・カテゴリ選択を初期表示する", async () => {
    await renderLoaded();
    expect(screen.getByText(/guide\.pdf（10\.0MB）/)).not.toBeNull();
    expect((screen.getByLabelText("カテゴリ") as HTMLSelectElement).disabled).toBe(false);
    expect((screen.getByLabelText("カテゴリ") as HTMLSelectElement).value).toBe("7");
    expect((screen.getByLabelText("対象者") as HTMLSelectElement).value).toBe("10");
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("実値差分だけでdirtyを判定し、元へ戻すと解除する", async () => {
    await renderLoaded();
    const category = screen.getByLabelText("カテゴリ");
    fireEvent.change(category, { target: { value: "" } });
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(category, { target: { value: "7" } });
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
    const title = screen.getByLabelText("タイトル");
    fireEvent.change(title, { target: { value: "変更" } });
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(title, { target: { value: "募集要項" } });
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("タイトル空欄、種別解除、優先度、各トグルとversionを更新する", async () => {
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("対象者"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("回答利用の優先度"), { target: { value: "HIGH" } });
    const switches = screen.getAllByRole("switch");
    fireEvent.click(switches[0]);
    fireEvent.click(switches[1]);
    fireEvent.click(screen.getByRole("button", { name: "更新する" }));
    await waitFor(() => expect(api.updateFileDataSource).toHaveBeenCalledWith(1, expect.objectContaining({
      title: "", type_1_value_id: null, priority: "HIGH", answer_source_enabled: false,
      category_id: 7, reference_link_visible: false, version: 2,
    })));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("更新中は二重送信と入力・戻る操作を禁止する", async () => {
    let resolve!: (value: typeof row) => void;
    api.updateFileDataSource.mockReturnValue(new Promise((done) => { resolve = done; }));
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "変更" } });
    const update = screen.getByRole("button", { name: "更新する" });
    fireEvent.click(update);
    expect((screen.getByLabelText("タイトル") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "データソース一覧に戻る" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(update);
    expect(api.updateFileDataSource).toHaveBeenCalledTimes(1);
    resolve({ ...row, title: "変更", version: 3 });
    await waitFor(() => expect(push).toHaveBeenCalledWith("/data-sources"));
  });

  it("dirty時は戻る・パンくず・Sidebarで未保存Modalを表示する", async () => {
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "変更" } });
    fireEvent.click(screen.getByRole("button", { name: "データソース一覧に戻る" }));
    let dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("情報を更新せずにデータソース一覧に戻ります。よろしいですか？")).not.toBeNull();
    fireEvent.click(within(dialog).getByRole("button", { name: "キャンセル" }));
    fireEvent.click(screen.getByRole("button", { name: "データソース一覧" }));
    dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "キャンセル" }));
    fireEvent.click(screen.getByRole("button", { name: "ダッシュボード" }));
    dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "一覧に戻る" }));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("dirty時だけbeforeunloadを抑止する", async () => {
    await renderLoaded();
    const cleanEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(cleanEvent);
    expect(cleanEvent.defaultPrevented).toBe(false);
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "変更" } });
    const dirtyEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(dirtyEvent);
    expect(dirtyEvent.defaultPrevented).toBe(true);
  });

  it("version競合と取得失敗、WEB対象外を表示する", async () => {
    api.updateFileDataSource.mockRejectedValue(new DataSourcesApiError("競合", 409, "VERSION_CONFLICT"));
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "変更" } });
    fireEvent.click(screen.getByRole("button", { name: "更新する" }));
    expect(await screen.findByText("他の操作で情報が更新されています。再読み込みしてください。")).not.toBeNull();
    cleanup();

    api.fetchDataSource.mockRejectedValue(new DataSourcesApiError("指定されたデータソースが見つかりません。", 404));
    render(<DataSourceFileEditPage />);
    expect(await screen.findByText("指定されたデータソースが見つかりません。")).not.toBeNull();
    cleanup();

    api.fetchDataSource.mockResolvedValue({ ...row, source_type: "WEB", file: null, website: { url: "https://example.com", last_fetched_at: null } });
    render(<DataSourceFileEditPage />);
    expect(await screen.findByText("ファイル編集の対象ではありません。")).not.toBeNull();
  });
});
