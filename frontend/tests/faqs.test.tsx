import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const faqApi = vi.hoisted(() => ({ fetchFaqs: vi.fn(), fetchFaq: vi.fn(), deleteFaq: vi.fn(), bulkDeleteFaqs: vi.fn(), exportFaqs: vi.fn() }));
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
const detail = {
  ...rows[0],
  answer: "回答1行目\nhttp://example.com/info。\nhttps://example.org/guide\njavascript:alert(1)",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-19T01:00:00Z",
  similar_questions: [
    { id: 12, question: "類似B", display_order: 2 },
    { id: 11, question: "類似A", display_order: 1 },
  ],
  classifications: [
    { type_code: "FAQ_TYPE_1", classification_type_id: 1, classification_value_id: 10, display_label: "表示区分1", value_name: "値1" },
    { type_code: "FAQ_TYPE_3", classification_type_id: 3, classification_value_id: 30, display_label: "表示区分3", value_name: "値3" },
  ],
};

beforeEach(() => {
  push.mockReset();
  Object.values(faqApi).forEach((mock) => mock.mockReset());
  classificationApi.fetchFaqClassifications.mockReset();
  faqApi.fetchFaqs.mockResolvedValue(result);
  faqApi.fetchFaq.mockResolvedValue(detail);
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

  it("Excel、新規、編集、区分設定、一括未実装導線が動作する", async () => {
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "一覧をダウンロード" }));
    await waitFor(() => expect(faqApi.exportFaqs).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole("button", { name: "FAQ新規追加" }));
    expect(push).toHaveBeenCalledWith("/faqs/new");
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "編集" }));
    expect(push).toHaveBeenCalledWith("/faqs/1/edit");
    fireEvent.click(screen.getByRole("button", { name: "区分を設定する" }));
    expect(push).toHaveBeenCalledWith("/faq-classifications");
  });

  it("参照Modalをページ遷移なしで開き、GET中の連打を抑止する", async () => {
    let resolveDetail: ((value: typeof detail) => void) | undefined;
    faqApi.fetchFaq.mockReturnValue(new Promise((resolve) => { resolveDetail = resolve; }));
    await renderPage();
    const trigger = within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" });
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog")).not.toBeNull();
    expect(screen.getByText("読み込み中...")).not.toBeNull();
    fireEvent.click(trigger);
    expect(faqApi.fetchFaq).toHaveBeenCalledOnce();
    expect(faqApi.fetchFaq).toHaveBeenCalledWith(1);
    expect(push).not.toHaveBeenCalled();
    resolveDetail?.(detail);
    expect(await screen.findByText("回答1行目", { exact: false })).not.toBeNull();
  });

  it("ID・全文・URL・類似質問順・動的区分・未選択・公開・日時を読み取り専用表示する", async () => {
    await renderPage();
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("回答1行目", { exact: false });
    expect(within(dialog).getByText("FAQ参照")).not.toBeNull();
    expect(within(dialog).getByText("1")).not.toBeNull();
    expect(within(dialog).getByText("申請期限は？")).not.toBeNull();
    const http = within(dialog).getByRole("link", { name: "http://example.com/info" });
    const https = within(dialog).getByRole("link", { name: "https://example.org/guide" });
    expect(http.getAttribute("target")).toBe("_blank");
    expect(http.getAttribute("rel")).toBe("noopener noreferrer");
    expect(https.getAttribute("href")).toBe("https://example.org/guide");
    expect(within(dialog).queryByRole("link", { name: /javascript/ })).toBeNull();
    expect(within(dialog).getByText(/javascript:alert/)).not.toBeNull();
    const similarA = within(dialog).getByText("類似A");
    const similarB = within(dialog).getByText("類似B");
    expect(similarA.compareDocumentPosition(similarB) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
    for (let index = 1; index <= 4; index += 1) expect(within(dialog).getByText(`表示区分${index}`)).not.toBeNull();
    expect(within(dialog).getByText("値1")).not.toBeNull();
    expect(within(dialog).getByText("値3")).not.toBeNull();
    expect(within(dialog).getByText("公開")).not.toBeNull();
    expect(within(dialog).getByText("2026/08/19 10:00")).not.toBeNull();
    expect(within(dialog).queryByRole("textbox")).toBeNull();
  });

  it("類似質問0件と非公開を空表示のまま扱う", async () => {
    faqApi.fetchFaq.mockResolvedValue({ ...detail, similar_questions: [], chat_enabled: false, classifications: [] });
    await renderPage();
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("非公開")).not.toBeNull();
    expect(within(dialog).queryByText("類似質問はありません")).toBeNull();
  });

  it("閉じる・Esc・背景クリックで閉じ、起動元へフォーカスを戻す", async () => {
    await renderPage();
    const trigger = within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" });
    trigger.focus();
    fireEvent.click(trigger);
    await screen.findByText("回答1行目", { exact: false });
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(trigger);

    fireEvent.click(trigger);
    await screen.findByText("回答1行目", { exact: false });
    fireEvent.mouseDown(screen.getByRole("presentation"));
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(trigger);
    await screen.findByText("回答1行目", { exact: false });
    const closeButtons = within(screen.getByRole("dialog")).getAllByRole("button", { name: "閉じる" });
    fireEvent.click(closeButtons.at(-1)!);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("編集するで参照Modalを閉じてCB-210へ遷移する", async () => {
    await renderPage();
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("回答1行目", { exact: false });
    fireEvent.click(within(dialog).getByRole("button", { name: "編集する" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(push).toHaveBeenCalledWith("/faqs/1/edit");
  });

  it("参照Modalから削除確認へ切り替え、成功後に一覧と総数を更新して安全な位置へフォーカスする", async () => {
    faqApi.fetchFaqs.mockResolvedValueOnce(result).mockResolvedValueOnce({ ...result, items: [rows[1]], total_count: 1 });
    await renderPage();
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" }));
    let dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("回答1行目", { exact: false });
    fireEvent.click(within(dialog).getByRole("button", { name: "削除する" }));
    dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/この操作は元に戻せません/)).not.toBeNull();
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    fireEvent.click(within(dialog).getByRole("button", { name: "削除する" }));
    await waitFor(() => expect(faqApi.deleteFaq).toHaveBeenCalledWith(1, 2));
    await waitFor(() => expect(screen.queryByText("申請期限は？")).toBeNull());
    expect(screen.getAllByText(/FAQ数/)[0].textContent).toContain("1件");
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("button", { name: "FAQ新規追加" })));
  });

  it("参照からの削除404／409をModal内に表示し、二重送信とEscを禁止する", async () => {
    let rejectDelete: ((reason: Error) => void) | undefined;
    faqApi.deleteFaq.mockReturnValue(new Promise<void>((_, reject) => { rejectDelete = reject; }));
    await renderPage();
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" }));
    let dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("回答1行目", { exact: false });
    fireEvent.click(within(dialog).getByRole("button", { name: "削除する" }));
    dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "削除する" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "削除する" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(faqApi.deleteFaq).toHaveBeenCalledOnce();
    expect(screen.getByRole("dialog")).not.toBeNull();
    rejectDelete?.(new FaqApiError("指定されたFAQが見つかりません。", 404, "FAQ_NOT_FOUND"));
    expect(await screen.findByText("指定されたFAQが見つかりません。")).not.toBeNull();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "キャンセル" }));

    faqApi.deleteFaq.mockRejectedValueOnce(new FaqApiError("競合", 409, "FAQ_VERSION_CONFLICT"));
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" }));
    dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("回答1行目", { exact: false });
    fireEvent.click(within(dialog).getByRole("button", { name: "削除する" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "削除する" }));
    expect(await screen.findByText("他の操作で情報が更新されています。再読み込みしてください。")).not.toBeNull();
  });

  it("参照を閉じても検索・sort・page・page_size・選択状態を維持する", async () => {
    faqApi.fetchFaqs.mockImplementation(async (filters) => ({ ...result, page: filters.page, page_size: filters.page_size, total_pages: 2 }));
    await renderPage();
    fireEvent.change(screen.getByPlaceholderText("質問／回答のキーワードを入力"), { target: { value: "保持する条件" } });
    fireEvent.click(screen.getByRole("button", { name: /ID/ }));
    await waitFor(() => expect(faqApi.fetchFaqs).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "id", order: "asc" })));
    await screen.findByRole("button", { name: "次へ" });
    fireEvent.change(screen.getByLabelText("表示件数"), { target: { value: "20" } });
    await waitFor(() => expect(faqApi.fetchFaqs).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, page_size: 20 })));
    await screen.findByRole("button", { name: "次へ" });
    fireEvent.click(screen.getByRole("button", { name: "次へ" }));
    await waitFor(() => expect(faqApi.fetchFaqs).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, page_size: 20 })));
    await screen.findByLabelText("申請期限は？を選択");
    fireEvent.click(screen.getByLabelText("申請期限は？を選択"));
    await waitFor(() => expect((screen.getByLabelText("申請期限は？を選択") as HTMLInputElement).checked).toBe(true));
    const callsBeforeReference = faqApi.fetchFaqs.mock.calls.length;
    fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" }));
    await screen.findByText("回答1行目", { exact: false });
    fireEvent.keyDown(document, { key: "Escape" });
    expect((screen.getByPlaceholderText("質問／回答のキーワードを入力") as HTMLInputElement).value).toBe("保持する条件");
    expect((screen.getByLabelText("表示件数") as HTMLSelectElement).value).toBe("20");
    expect((screen.getByLabelText("申請期限は？を選択") as HTMLInputElement).checked).toBe(true);
    expect(faqApi.fetchFaqs.mock.calls.length).toBe(callsBeforeReference);
    expect(faqApi.fetchFaqs).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "id", page: 2, page_size: 20 }));
  });

  it("詳細404・通信失敗を壊れた空Modalにせず表示する", async () => {
    for (const failure of [
      new FaqApiError("指定されたFAQが見つかりません。", 404, "FAQ_NOT_FOUND"),
      new Error("FAQの取得に失敗しました。"),
    ]) {
      faqApi.fetchFaq.mockRejectedValueOnce(failure);
      await renderPage();
      fireEvent.click(within(screen.getByText("申請期限は？").closest("tr")!).getByRole("button", { name: "参照" }));
      expect(await screen.findByText(failure.message)).not.toBeNull();
      expect(within(screen.getByRole("dialog")).getByRole("button", { name: "編集する" }).hasAttribute("disabled")).toBe(true);
      fireEvent.keyDown(document, { key: "Escape" });
      cleanup();
    }
  });
});
