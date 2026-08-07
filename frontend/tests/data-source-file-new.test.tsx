import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DataSourceFileNewPage from "@/app/data-sources/files/new/page";

const push = vi.fn();
const api = vi.hoisted(() => ({ fetchDataSourceTypes: vi.fn(), createFileDataSources: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", () => ({ fetchDataSourceTypes: api.fetchDataSourceTypes }));
vi.mock("@/lib/dataSourceFilesApi", () => ({ createFileDataSources: api.createFileDataSources }));

const types = [{ id: 1, type_code: "TYPE_1", fixed_name: "種別1", display_label: "対象者", display_order: 1, version: 1, values: [{ id: 10, value_name: "在学生", display_order: 1, version: 1 }] }];

function textFile(name: string, content = "text") {
  const bytes = new TextEncoder().encode(content);
  const value = new File([bytes], name, { type: "text/plain" });
  Object.defineProperty(value, "arrayBuffer", { value: async () => bytes.buffer });
  return value;
}

beforeEach(() => {
  push.mockReset();
  api.fetchDataSourceTypes.mockReset().mockResolvedValue(types);
  api.createFileDataSources.mockReset().mockResolvedValue({ items: [], created_count: 1 });
});
afterEach(cleanup);

function renderPage() {
  render(<DataSourceFileNewPage />);
  return document.querySelector<HTMLInputElement>('input[type="file"]')!;
}
async function choose(input: HTMLInputElement, files: File[]) {
  fireEvent.change(input, { target: { files } });
  await screen.findByText(new RegExp(`選択中のファイル（サイズ）：${files.length}件`));
}

describe("CB-203 file add page", () => {
  it("初期値と種別ラベルを表示する", async () => {
    renderPage();
    expect((screen.getByRole("button", { name: "ファイルを追加する" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText("回答利用の優先度") as HTMLSelectElement).value).toBe("MEDIUM");
    expect(screen.getAllByRole("switch").map((item) => item.getAttribute("aria-checked"))).toEqual(["true", "true"]);
    expect(await screen.findByLabelText("対象者")).not.toBeNull();
    expect((screen.getByLabelText("カテゴリ") as HTMLSelectElement).disabled).toBe(true);
  });

  it("ファイル選択・一覧・個別解除とタイトル活性を管理する", async () => {
    const input = renderPage();
    await choose(input, [textFile("one.txt")]);
    expect((screen.getByLabelText("タイトル") as HTMLInputElement).disabled).toBe(false);
    expect(screen.getByText(/one.txt/)).not.toBeNull();
    await choose(input, [textFile("two.txt")]);
    expect((screen.getByLabelText("タイトル") as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "two.txtを選択から外す" }));
    expect((screen.getByLabelText("タイトル") as HTMLInputElement).disabled).toBe(false);
  });

  it("ドラッグ＆ドロップで追加する", async () => {
    renderPage();
    const dropzone = screen.getByRole("group", { name: /ドラッグ＆ドロップ/ });
    fireEvent.drop(dropzone, { dataTransfer: { files: [textFile("drop.txt")] } });
    expect(await screen.findByText(/drop.txt/)).not.toBeNull();
  });

  it("登録時に値を送信し成功後一覧へ遷移する", async () => {
    const input = renderPage();
    await choose(input, [textFile("one.txt")]);
    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "任意タイトル" } });
    fireEvent.change(await screen.findByLabelText("対象者"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "ファイルを追加する" }));
    await waitFor(() => expect(api.createFileDataSources).toHaveBeenCalledWith(expect.objectContaining({ title: "任意タイトル", type_1_value_id: "10", priority: "MEDIUM" })));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("登録失敗を表示し二重送信を防ぐ", async () => {
    let reject!: (error: Error) => void;
    api.createFileDataSources.mockReturnValue(new Promise((_, promiseReject) => { reject = promiseReject; }));
    const input = renderPage();
    await choose(input, [textFile("one.txt")]);
    const submit = screen.getByRole("button", { name: "ファイルを追加する" });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(api.createFileDataSources).toHaveBeenCalledTimes(1);
    reject(new Error("ファイルの追加に失敗しました。"));
    expect(await screen.findByRole("alert")).not.toBeNull();
  });

  it("未保存時は各離脱操作でModalを表示し、未選択なら直接戻る", async () => {
    const input = renderPage();
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(push).toHaveBeenCalledWith("/data-sources");
    push.mockReset();
    await choose(input, [textFile("one.txt")]);
    fireEvent.click(screen.getByRole("button", { name: "データソース一覧に戻る" }));
    expect(screen.getByRole("dialog")).not.toBeNull();
    expect(screen.getByText("ファイルを追加せずにデータソース一覧に戻ります。よろしいですか？")).not.toBeNull();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "キャンセル" }));
    fireEvent.click(screen.getByRole("button", { name: "データソース一覧" }));
    fireEvent.click(screen.getByRole("button", { name: "一覧に戻る" }));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("ファイル選択時はbeforeunloadを抑止する", async () => {
    const input = renderPage();
    await choose(input, [textFile("one.txt")]);
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });

  it("Sidebar離脱でも未保存確認を表示する", async () => {
    const input = renderPage();
    await choose(input, [textFile("one.txt")]);
    fireEvent.click(screen.getByRole("button", { name: "ダッシュボード" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "一覧に戻る" }));
    expect(push).toHaveBeenCalledWith("/");
  });
});
