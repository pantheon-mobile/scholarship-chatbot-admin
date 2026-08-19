import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const api = vi.hoisted(() => ({ createFaq: vi.fn() }));
const classificationApi = vi.hoisted(() => ({ fetchFaqClassifications: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("../lib/faqsApi", () => ({ ...api }));
vi.mock("../lib/faqClassificationsApi", () => ({ ...classificationApi }));

import FaqNewPage from "../app/faqs/new/page";
import { FaqApiError } from "../types/faq";

const types = [1,2,3,4].map((index) => ({
  id: index, type_code: `FAQ_TYPE_${index}`, fixed_name: `区分${index}`,
  display_label: `表示区分${index}`, display_order: index, version: 1,
  values: index === 4 ? [] : [{ id: index * 10, value_name: `値${index}`, display_order: 1, version: 1 }],
}));

beforeEach(() => {
  push.mockReset();
  api.createFaq.mockReset();
  classificationApi.fetchFaqClassifications.mockReset();
  classificationApi.fetchFaqClassifications.mockResolvedValue(types);
  api.createFaq.mockResolvedValue({ id: 1 });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function renderPage() {
  render(<FaqNewPage />);
  await screen.findByLabelText("表示区分1");
}
function fillRequired(question = "質問", answer = "回答") {
  fireEvent.change(screen.getByLabelText("質問"), { target: { value: question } });
  fireEvent.change(screen.getByLabelText("回答"), { target: { value: answer } });
}

describe("CB-209 FAQ registration", () => {
  it("ID、質問・回答、カウンター、公開初期値、現行Header/Sidebarを表示する", async () => {
    await renderPage();
    expect(screen.getByText("－")).not.toBeNull();
    expect(screen.getByText("0 / 500")).not.toBeNull();
    expect(screen.getByText("0 / 1000")).not.toBeNull();
    expect(screen.queryByLabelText("類似質問1")).toBeNull();
    expect(screen.getByText("公開")).not.toBeNull();
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("true");
    expect(screen.getByRole("button", { name: "登録する" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "チャットサイト" })).not.toBeNull();
    expect(screen.getByText("ＦＡＱ管理")).not.toBeNull();
  });

  it("500／1000文字境界を許可し、超過時はエラーと登録disabledにする", async () => {
    await renderPage();
    fillRequired("q".repeat(500), "a".repeat(1000));
    expect(screen.getByText("500 / 500")).not.toBeNull();
    expect(screen.getByText("1000 / 1000")).not.toBeNull();
    expect(screen.getByRole("button", { name: "登録する" }).hasAttribute("disabled")).toBe(false);
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "q".repeat(501) } });
    fireEvent.blur(screen.getByLabelText("質問"));
    expect(screen.getByText("501 / 500")).not.toBeNull();
    expect(screen.getByText("質問は500文字以内で入力してください。")).not.toBeNull();
    expect(screen.getByRole("button", { name: "登録する" }).hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "質問" } });
    fireEvent.change(screen.getByLabelText("回答"), { target: { value: "a".repeat(1001) } });
    fireEvent.blur(screen.getByLabelText("回答"));
    expect(screen.getByText("1001 / 1000")).not.toBeNull();
    expect(screen.getByText("回答は1000文字以内で入力してください。")).not.toBeNull();
  });

  it("類似質問を複数追加・個別削除し、文字数と空行validationを表示する", async () => {
    await renderPage();
    fillRequired();
    fireEvent.click(screen.getByRole("button", { name: "類似質問を追加" }));
    fireEvent.click(screen.getByRole("button", { name: "類似質問を追加" }));
    expect(screen.getByLabelText("類似質問2")).not.toBeNull();
    fireEvent.blur(screen.getByLabelText("類似質問1"));
    expect(screen.getByText("類似質問を入力してください。")).not.toBeNull();
    fireEvent.change(screen.getByLabelText("類似質問1"), { target: { value: "類似" } });
    expect(screen.getAllByText("2 / 500").length).toBeGreaterThan(0);
    const firstRow = screen.getByLabelText("類似質問1").closest("div")!;
    fireEvent.click(within(firstRow).getByRole("button", { name: "削除" }));
    expect(screen.getAllByLabelText(/類似質問/)).toHaveLength(1);
    fireEvent.change(screen.getByLabelText("類似質問1"), { target: { value: "x".repeat(501) } });
    fireEvent.blur(screen.getByLabelText("類似質問1"));
    expect(screen.getByText("類似質問は500文字以内で入力してください。")).not.toBeNull();
  });

  it("動的な4区分と値0件を表示し、Toggleを変更できる", async () => {
    await renderPage();
    expect(screen.getByLabelText("表示区分1")).not.toBeNull();
    expect(within(screen.getByLabelText("表示区分1")).getByRole("option", { name: "値1" })).not.toBeNull();
    expect(within(screen.getByLabelText("表示区分4")).getAllByRole("option")).toHaveLength(1);
    fireEvent.click(screen.getByRole("switch"));
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText("非公開")).not.toBeNull();
  });

  it("trim済み値・類似順序・4区分・非公開を登録して一覧へ戻る", async () => {
    await renderPage();
    fillRequired(" 質問 ", " 回答\n本文 ");
    fireEvent.click(screen.getByRole("button", { name: "類似質問を追加" }));
    fireEvent.change(screen.getByLabelText("類似質問1"), { target: { value: " 類似1 " } });
    fireEvent.change(screen.getByLabelText("表示区分1"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("表示区分2"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("表示区分3"), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("switch"));
    fireEvent.click(screen.getByRole("button", { name: "登録する" }));
    await waitFor(() => expect(api.createFaq).toHaveBeenCalledWith({
      question: "質問", answer: "回答\n本文", similar_questions: ["類似1"],
      classification_1_value_id: 10, classification_2_value_id: 20,
      classification_3_value_id: 30, classification_4_value_id: null, chat_enabled: false,
    }));
    expect(push).toHaveBeenCalledWith("/faqs");
  });

  it("登録中は二重送信と入力・離脱操作を無効化する", async () => {
    let resolveCreate: ((value: unknown) => void) | undefined;
    api.createFaq.mockReturnValue(new Promise((resolve) => { resolveCreate = resolve; }));
    await renderPage();
    fillRequired();
    fireEvent.click(screen.getByRole("button", { name: "登録する" }));
    expect(await screen.findByRole("button", { name: "登録中..." })).not.toBeNull();
    expect((screen.getByLabelText("質問") as HTMLTextAreaElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "キャンセル" }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "登録中..." }));
    expect(api.createFaq).toHaveBeenCalledOnce();
    resolveCreate?.({ id: 1 });
    await waitFor(() => expect(push).toHaveBeenCalledWith("/faqs"));
  });

  it("API validationを該当項目へ表示し、登録失敗時は画面に残る", async () => {
    api.createFaq.mockRejectedValueOnce(new FaqApiError("質問は500文字以内で入力してください。", 422, "FAQ_QUESTION_TOO_LONG"));
    await renderPage();
    fillRequired();
    fireEvent.click(screen.getByRole("button", { name: "登録する" }));
    expect(await screen.findByText("質問は500文字以内で入力してください。")).not.toBeNull();
    expect(push).not.toHaveBeenCalledWith("/faqs");
  });

  it("dirty時の一覧・キャンセル・Sidebar離脱で未保存Modalを表示する", async () => {
    await renderPage();
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "入力中" } });
    fireEvent.click(screen.getByRole("button", { name: "FAQ一覧へ戻る" }));
    expect(screen.getByText("FAQを登録せずにFAQ一覧に戻ります。よろしいですか？")).not.toBeNull();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "キャンセル" }));
    fireEvent.click(screen.getByRole("button", { name: "データソース管理" }));
    expect(screen.getByText("入力内容を保存せずに移動します。よろしいですか？")).not.toBeNull();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "移動する" }));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("入力を初期状態へ戻すとdirty=falseになり即時遷移する", async () => {
    await renderPage();
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "入力" } });
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "FAQ一覧へ戻る" }));
    expect(push).toHaveBeenCalledWith("/faqs");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("dirty時だけbeforeunloadを抑止する", async () => {
    await renderPage();
    const cleanEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(cleanEvent);
    expect(cleanEvent.defaultPrevented).toBe(false);
    fireEvent.change(screen.getByLabelText("回答"), { target: { value: "入力" } });
    const dirtyEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(dirtyEvent);
    expect(dirtyEvent.defaultPrevented).toBe(true);
  });
});
