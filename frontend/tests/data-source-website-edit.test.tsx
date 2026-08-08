import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DataSourceWebsiteEditPage from "@/app/data-sources/[id]/website/edit/page";
import { DataSourcesApiError } from "@/types/dataSource";

const push = vi.fn();
const api = vi.hoisted(() => ({ fetchDataSource: vi.fn(), updateWebsiteDataSource: vi.fn(), fetchDataSourceTypes: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }), useParams: () => ({ id: "8" }) }));
vi.mock("@/lib/dataSourcesApi", async () => {
  const actual = await vi.importActual<typeof import("@/lib/dataSourcesApi")>("@/lib/dataSourcesApi");
  return { ...actual, fetchDataSource: api.fetchDataSource, updateWebsiteDataSource: api.updateWebsiteDataSource };
});
vi.mock("@/lib/api", () => ({ fetchDataSourceTypes: api.fetchDataSourceTypes }));

const types = [
  { id: 1, type_code: "TYPE_1", fixed_name: "種別1", display_label: "対象者", display_order: 1, version: 1, values: [{ id: 10, value_name: "在学生", display_order: 1, version: 1 }, { id: 11, value_name: "卒業生", display_order: 2, version: 1 }] },
  { id: 2, type_code: "TYPE_2", fixed_name: "種別2", display_label: "給付区分", display_order: 2, version: 1, values: [{ id: 20, value_name: "給付", display_order: 1, version: 1 }] },
  { id: 3, type_code: "TYPE_3", fixed_name: "種別3", display_label: "所属", display_order: 3, version: 1, values: [{ id: 30, value_name: "学部", display_order: 1, version: 1 }] },
];
const row = {
  id: 8, source_type: "WEB" as const, title: "奨学金情報", format: "Web", status: "AVAILABLE" as const,
  category_name: "既存カテゴリ", size_bytes: null, character_count: 4321,
  answer_source_enabled: true, priority: "LOW" as const, reference_link_visible: false,
  updated_at: "2026-08-07T01:00:00Z", version: 2, file: null,
  website: { url: "https://old.example.com", last_fetched_at: "2026-08-06T01:00:00Z" },
  classifications: [{ type_code: "TYPE_1", classification_type_id: 1, classification_value_id: 10, display_label: "対象者", value_name: "在学生" }],
};

beforeEach(() => {
  push.mockReset();
  api.fetchDataSource.mockReset().mockResolvedValue(row);
  api.fetchDataSourceTypes.mockReset().mockResolvedValue(types);
  api.updateWebsiteDataSource.mockReset().mockResolvedValue({ ...row, website: { ...row.website, url: "https://new.example.com" }, version: 3 });
});
afterEach(cleanup);

async function renderLoaded() {
  render(<DataSourceWebsiteEditPage />);
  await screen.findByDisplayValue("https://old.example.com");
}

describe("CB-206 website edit page", () => {
  it("現在のURL・属性・種別とdisabledカテゴリを初期表示する", async () => {
    await renderLoaded();
    expect((screen.getByLabelText("タイトル") as HTMLInputElement).value).toBe("奨学金情報");
    expect((screen.getByLabelText("カテゴリ") as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByLabelText("カテゴリ") as HTMLSelectElement).value).toBe("既存カテゴリ");
    expect((screen.getByLabelText("対象者") as HTMLSelectElement).value).toBe("10");
    expect((screen.getByLabelText("回答利用の優先度") as HTMLSelectElement).value).toBe("LOW");
    expect(screen.getAllByRole("switch").map((item) => item.getAttribute("aria-checked"))).toEqual(["true", "false"]);
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("実値差分だけでdirtyを判定し元へ戻すと解除する", async () => {
    await renderLoaded();
    const title = screen.getByLabelText("タイトル");
    fireEvent.change(title, { target: { value: "変更" } });
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(title, { target: { value: "奨学金情報" } });
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("URL空で更新を無効化し不正URLを送信前に拒否する", async () => {
    await renderLoaded();
    const url = screen.getByLabelText("WebサイトURL");
    fireEvent.change(url, { target: { value: "" } });
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(url, { target: { value: "ftp://example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "更新する" }));
    expect((await screen.findByRole("alert")).textContent).toContain("正しいURLを入力してください。");
    expect(api.updateWebsiteDataSource).not.toHaveBeenCalled();
  });

  it("URL・空タイトル・種別解除・優先度・トグルとversionを更新する", async () => {
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("WebサイトURL"), { target: { value: "  https://new.example.com  " } });
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("対象者"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("回答利用の優先度"), { target: { value: "HIGH" } });
    fireEvent.click(screen.getAllByRole("switch")[0]);
    fireEvent.click(screen.getAllByRole("switch")[1]);
    fireEvent.click(screen.getByRole("button", { name: "更新する" }));
    await waitFor(() => expect(api.updateWebsiteDataSource).toHaveBeenCalledWith(8, expect.objectContaining({
      url: "https://new.example.com", title: "", type_1_value_id: null, priority: "HIGH",
      answer_source_enabled: false, reference_link_visible: true, version: 2,
    })));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("更新中は入力・戻る・二重送信を禁止する", async () => {
    let resolve!: (value: typeof row) => void;
    api.updateWebsiteDataSource.mockReturnValue(new Promise((done) => { resolve = done; }));
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "変更" } });
    const update = screen.getByRole("button", { name: "更新する" });
    fireEvent.click(update);
    expect((screen.getByLabelText("WebサイトURL") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "データソース一覧に戻る" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(update);
    expect(api.updateWebsiteDataSource).toHaveBeenCalledTimes(1);
    resolve({ ...row, title: "変更", version: 3 });
    await waitFor(() => expect(push).toHaveBeenCalledWith("/data-sources"));
  });

  it("取得失敗・FILE対象外・version競合・更新失敗を表示する", async () => {
    api.updateWebsiteDataSource.mockRejectedValue(new DataSourcesApiError("競合", 409, "VERSION_CONFLICT"));
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "変更" } });
    fireEvent.click(screen.getByRole("button", { name: "更新する" }));
    expect(await screen.findByText("他の操作で情報が更新されています。再読み込みしてください。")).not.toBeNull();
    cleanup();

    api.fetchDataSource.mockRejectedValue(new DataSourcesApiError("指定されたデータソースが見つかりません。", 404));
    render(<DataSourceWebsiteEditPage />);
    expect(await screen.findByText("指定されたデータソースが見つかりません。")).not.toBeNull();
    cleanup();

    api.fetchDataSource.mockResolvedValue({ ...row, source_type: "FILE", website: null, file: { file_name: "guide.pdf" } });
    render(<DataSourceWebsiteEditPage />);
    expect(await screen.findByText("Webサイト編集の対象ではありません。")).not.toBeNull();
  });

  it("dirty時は各離脱操作とbeforeunloadで確認する", async () => {
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "変更" } });
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
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
});
