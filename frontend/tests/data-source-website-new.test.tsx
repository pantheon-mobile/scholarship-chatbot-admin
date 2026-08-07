import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DataSourceWebsiteNewPage from "@/app/data-sources/websites/new/page";

const push = vi.fn();
const api = vi.hoisted(() => ({ fetchDataSourceTypes: vi.fn(), createWebsiteDataSource: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", () => ({ fetchDataSourceTypes: api.fetchDataSourceTypes }));
vi.mock("@/lib/dataSourcesApi", () => ({ createWebsiteDataSource: api.createWebsiteDataSource }));

const types = [
  { id: 1, type_code: "TYPE_1", fixed_name: "種別1", display_label: "対象者", display_order: 1, version: 1, values: [{ id: 10, value_name: "在学生", display_order: 1, version: 1 }] },
  { id: 2, type_code: "TYPE_2", fixed_name: "種別2", display_label: "給付区分", display_order: 2, version: 1, values: [{ id: 20, value_name: "給付", display_order: 1, version: 1 }] },
  { id: 3, type_code: "TYPE_3", fixed_name: "種別3", display_label: "所属", display_order: 3, version: 1, values: [{ id: 30, value_name: "学部", display_order: 1, version: 1 }] },
];

beforeEach(() => {
  push.mockReset();
  api.fetchDataSourceTypes.mockReset().mockResolvedValue(types);
  api.createWebsiteDataSource.mockReset().mockResolvedValue({ id: 1 });
});
afterEach(cleanup);

async function renderPage() {
  render(<DataSourceWebsiteNewPage />);
  await screen.findByLabelText("対象者");
}

describe("CB-205 website add page", () => {
  it("初期値・disabledカテゴリ・未選択種別を表示する", async () => {
    await renderPage();
    expect((screen.getByLabelText("カテゴリ") as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByLabelText("回答利用の優先度") as HTMLSelectElement).value).toBe("MEDIUM");
    expect((screen.getByLabelText("対象者") as HTMLSelectElement).value).toBe("");
    expect(screen.getAllByRole("switch").map((item) => item.getAttribute("aria-checked"))).toEqual(["true", "true"]);
    expect((screen.getByRole("button", { name: "Webサイトを追加する" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("URL、任意タイトル、種別、優先度、独立トグルを登録する", async () => {
    await renderPage();
    fireEvent.change(screen.getByLabelText("WebサイトURL"), { target: { value: "  https://example.com/scholarship  " } });
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "奨学金案内" } });
    fireEvent.change(screen.getByLabelText("対象者"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("給付区分"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("回答利用の優先度"), { target: { value: "HIGH" } });
    fireEvent.click(screen.getAllByRole("switch")[1]);
    fireEvent.click(screen.getByRole("button", { name: "Webサイトを追加する" }));
    await waitFor(() => expect(api.createWebsiteDataSource).toHaveBeenCalledWith({
      url: "https://example.com/scholarship", title: "奨学金案内",
      type_1_value_id: 10, type_2_value_id: 20, type_3_value_id: null,
      priority: "HIGH", answer_source_enabled: true, reference_link_visible: false,
    }));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("不正URLをクライアントで拒否し、タイトル空欄を許可する", async () => {
    await renderPage();
    fireEvent.change(screen.getByLabelText("WebサイトURL"), { target: { value: "ftp://example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Webサイトを追加する" }));
    expect((await screen.findByRole("alert")).textContent).toContain("正しいURLを入力してください。");
    expect(api.createWebsiteDataSource).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("WebサイトURL"), { target: { value: "https://example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Webサイトを追加する" }));
    await waitFor(() => expect(api.createWebsiteDataSource).toHaveBeenCalledWith(expect.objectContaining({ title: "" })));
  });

  it("登録中は入力・戻る・二重送信を禁止する", async () => {
    let resolve!: (value: { id: number }) => void;
    api.createWebsiteDataSource.mockReturnValue(new Promise((done) => { resolve = done; }));
    await renderPage();
    fireEvent.change(screen.getByLabelText("WebサイトURL"), { target: { value: "https://example.com" } });
    const submit = screen.getByRole("button", { name: "Webサイトを追加する" });
    fireEvent.click(submit);
    expect((screen.getByLabelText("WebサイトURL") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "データソース一覧に戻る" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(submit);
    expect(api.createWebsiteDataSource).toHaveBeenCalledTimes(1);
    resolve({ id: 1 });
    await waitFor(() => expect(push).toHaveBeenCalledWith("/data-sources"));
  });

  it("登録失敗を表示する", async () => {
    api.createWebsiteDataSource.mockRejectedValue(new Error("Webサイトの追加に失敗しました。"));
    await renderPage();
    fireEvent.change(screen.getByLabelText("WebサイトURL"), { target: { value: "https://example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Webサイトを追加する" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Webサイトの追加に失敗しました。");
  });

  it("初期値との差分だけをdirtyとし、戻すと確認なしになる", async () => {
    await renderPage();
    const url = screen.getByLabelText("WebサイトURL");
    fireEvent.change(url, { target: { value: "https://example.com" } });
    fireEvent.change(url, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(push).toHaveBeenCalledWith("/data-sources");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("dirty時は各離脱操作とbeforeunloadで確認する", async () => {
    await renderPage();
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "入力中" } });
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "データソース一覧に戻る" }));
    let dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Webサイトを追加せずにデータソース一覧に戻ります。よろしいですか？")).not.toBeNull();
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
