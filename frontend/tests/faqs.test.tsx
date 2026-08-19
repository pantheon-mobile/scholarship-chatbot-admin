import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const faqApi = vi.hoisted(() => ({ fetchFaqs: vi.fn(), deleteFaq: vi.fn(), bulkDeleteFaqs: vi.fn(), exportFaqs: vi.fn() }));
const classificationApi = vi.hoisted(() => ({ fetchFaqClassifications: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("../lib/faqsApi", () => ({ ...faqApi }));
vi.mock("../lib/faqClassificationsApi", () => ({ ...classificationApi }));

import FaqsPage from "../app/faqs/page";
import { FaqApiError } from "../types/faq";

const classificationTypes = [1, 2, 3, 4].map((index) => ({
  id: index, type_code: `FAQ_TYPE_${index}`, fixed_name: `区分${index}`, display_label: `表示区分${index}`,
  display_order: index, version: 1,
  values: [{ id: index * 10, value_name: `値${index}`, display_order: 1, version: 1 }],
}));
const rows = [
  { id: 1, question: "申請期限は？", answer: "8月末です。", chat_enabled: true, updated_at: "2026-08-19T01:00:00Z", version: 2, classifications: [{ type_code: "FAQ_TYPE_1", classification_type_id: 1, classification_value_id: 10, display_label: "表示区分1", value_name: "値1" }] },
  { id: 2, question: "必要書類は？", answer: "申請書です。", chat_enabled: false, updated_at: "2026-08-18T01:00:00Z", version: 1, classifications: [] },
];
const result = { items: rows, page: 1, page_size: 10, total_count: 2, total_pages: 1, sort: "updated_at", order: "desc" };

beforeEach(() => {
  push.mockReset();
  Object.values(faqApi).forEach((mock) => mock.mockReset());
  classificationApi.fetchFaqClassifications.mockReset();
  faqApi.fetchFaqs.mockResolvedValue(result);
  faqApi.deleteFaq.mockResolvedValue(undefined);
  faqApi.bulkDeleteFaqs.mockResolvedValue(2);
  faqApi.exportFaqs.mockResolvedValue(new Blob(["xlsx"]));
  classificationApi.fetchFaqClassifications.mockResolvedValue(classificationTypes);
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:faq") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function renderPage() {
  render(<FaqsPage />);
  await screen.findByText("申請期限は？");
}

describe("CB-208 FAQ list", () => {
  it("初期表示、総数、動的区分、公開状態、現行Header/Sidebarを表示する", async () => {
    await renderPage();
    expect(screen.getByRole("heading", { name: "FAQ一覧" })).not.toBeNull();
    expect(screen.getAllByText(/FAQ数/)[0].textContent).toContain("2件");
    expect(screen.getAllByText("表示区分4").length).toBeGreaterThan(0);
    expect(screen.getAllByText("値1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("公開").length).toBeGreaterThan(0);
    expect(screen.getAllByText("非公開").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "チャットサイト" })).not.toBeNull();
    expect(screen.getByText("ＦＡＱ管理")).not.toBeNull();
  });

  it("0件表示に対応する", async () => {
    faqApi.fetchFaqs.mockResolvedValueOnce({ ...result, items: [], total_count: 0, total_pages: 0 });
    render(<FaqsPage />);
    expect(await screen.findByText("FAQは登録されていません。")).not.toBeNull();
  });

  it("キーワード、4区分、チャット利用をAND検索条件として送る", async () => {
    await renderPage();
    fireEvent.change(screen.getByPlaceholderText("質問／回答のキーワードを入力"), { target: { value: "期限" } });
    for (let index = 1; index <= 4; index += 1) fireEvent.change(screen.getByLabelText(`表示区分${index}`), { target: { value: String(index * 10) } });
    fireEvent.change(screen.getByLabelText("チャット利用"), { target: { value: "true" } });
    fireEvent.click(screen.getByRole("button", { name: "絞り込み検索" }));
    await waitFor(() => expect(faqApi.fetchFaqs).toHaveBeenLastCalledWith(expect.objectContaining({
      keyword: "期限", classification_1_value_id: "10", classification_2_value_id: "20",
      classification_3_value_id: "30", classification_4_value_id: "40", chat_enabled: "true", page: 1,
    })));
  });

  it("ID・更新日時ソート、表示件数、ページングを更新する", async () => {
    faqApi.fetchFaqs.mockResolvedValue({ ...result, total_pages: 2 });
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: /ID/ }));
    await waitFor(() => expect(faqApi.fetchFaqs).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "id", order: "asc" })));
    fireEvent.change(screen.getByLabelText("表示件数"), { target: { value: "20" } });
    await waitFor(() => expect(faqApi.fetchFaqs).toHaveBeenLastCalledWith(expect.objectContaining({ page_size: 20 })));
    fireEvent.click(screen.getByRole("button", { name: "次へ" }));
    await waitFor(() => expect(faqApi.fetchFaqs).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("PAGE_NOT_FOUNDだけ共通Modalで表示する", async () => {
    faqApi.fetchFaqs.mockRejectedValueOnce(new FaqApiError("ページがありません。", 422, "PAGE_NOT_FOUND"));
    render(<FaqsPage />);
    expect(await screen.findByRole("dialog")).not.toBeNull();
    expect(screen.getByText("指定されたページは存在しません。")).not.toBeNull();
  });

  it("個別選択、全選択、全解除、indeterminateに対応する", async () => {
    await renderPage();
    const first = screen.getByLabelText("申請期限は？を選択");
    fireEvent.click(first);
    const masters = screen.getAllByLabelText("表示中ページを全選択") as HTMLInputElement[];
    expect(masters[0].indeterminate).toBe(true);
    fireEvent.click(masters[0]);
    expect((screen.getByLabelText("必要書類は？を選択") as HTMLInputElement).checked).toBe(true);
    fireEvent.click(masters[0]);
    expect((screen.getByLabelText("申請期限は？を選択") as HTMLInputElement).checked).toBe(false);
  });

  it("個別削除と一括削除をModalで実行し、削除中は閉じられない", async () => {
    let resolveDelete: (() => void) | undefined;
    faqApi.deleteFaq.mockReturnValue(new Promise<void>((resolve) => { resolveDelete = resolve; }));
    await renderPage();
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "削除" }));
    expect(screen.getByText(/この操作は元に戻せません/)).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog")).not.toBeNull();
    resolveDelete?.();
    await waitFor(() => expect(faqApi.deleteFaq).toHaveBeenCalledWith(1, 2));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    fireEvent.click(screen.getByLabelText("申請期限は？を選択"));
    fireEvent.click(screen.getByLabelText("必要書類は？を選択"));
    const bulkButton = screen.getAllByRole("button", { name: "削除" })[0];
    await waitFor(() => expect(bulkButton.hasAttribute("disabled")).toBe(false));
    fireEvent.click(bulkButton);
    expect(screen.getByRole("dialog").textContent).toContain("選択した2件のFAQを削除します。");
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));
    await waitFor(() => expect(faqApi.bulkDeleteFaqs).toHaveBeenCalledWith([{ id: 1, version: 2 }, { id: 2, version: 1 }]));
  });

  it("削除失敗をModal内に表示する", async () => {
    faqApi.deleteFaq.mockRejectedValueOnce(new Error("他の操作で情報が更新されています。再読み込みしてください。"));
    await renderPage();
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "削除" }));
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));
    expect(await screen.findByText("他の操作で情報が更新されています。再読み込みしてください。")).not.toBeNull();
    expect(screen.getByRole("dialog")).not.toBeNull();
  });

  it("Excel、新規、編集、区分設定、参照・一括未実装導線が動作する", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "一覧をダウンロード" }));
    await waitFor(() => expect(faqApi.exportFaqs).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole("button", { name: "FAQ新規追加" }));
    expect(push).toHaveBeenCalledWith("/faqs/new");
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "編集" }));
    expect(push).toHaveBeenCalledWith("/faqs/1/edit");
    fireEvent.click(screen.getByRole("button", { name: "区分を設定する" }));
    expect(push).toHaveBeenCalledWith("/faq-classifications");
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" }));
    expect(screen.getByText("FAQ参照Modalは未実装です。")).not.toBeNull();
  });
});
