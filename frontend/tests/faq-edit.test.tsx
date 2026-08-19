import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const api = vi.hoisted(() => ({ fetchFaq: vi.fn(), updateFaq: vi.fn() }));
const classificationApi = vi.hoisted(() => ({ fetchFaqClassifications: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }), useParams: () => ({ id: "1" }) }));
vi.mock("../lib/faqsApi", async () => {
  const actual = await vi.importActual<typeof import("../lib/faqsApi")>("../lib/faqsApi");
  return { ...actual, fetchFaq: api.fetchFaq, updateFaq: api.updateFaq };
});
vi.mock("../lib/faqClassificationsApi", () => ({ ...classificationApi }));

import FaqEditPage from "../app/faqs/[id]/edit/page";
import { FaqApiError, FaqDetail } from "../types/faq";

const types = [1,2,3,4].map((index) => ({
  id: index, type_code: `FAQ_TYPE_${index}`, fixed_name: `区分${index}`,
  display_label: `表示区分${index}`, display_order: index, version: 1,
  values: [{ id: index * 10, value_name: `値${index}`, display_order: 1, version: 1 },
    { id: index * 10 + 1, value_name: `変更値${index}`, display_order: 2, version: 1 }],
}));

const row: FaqDetail = {
  id: 1, question: "申請期限は？", answer: "8月末です。\n期限厳守です。", chat_enabled: false,
  created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-19T01:02:00Z", version: 2,
  similar_questions: [
    { id: 12, question: "類似B", display_order: 2 },
    { id: 11, question: "類似A", display_order: 1 },
  ],
  classifications: [
    { type_code: "FAQ_TYPE_1", classification_type_id: 1, classification_value_id: 10, display_label: "表示区分1", value_name: "値1" },
    { type_code: "FAQ_TYPE_4", classification_type_id: 4, classification_value_id: 40, display_label: "表示区分4", value_name: "値4" },
  ],
};

beforeEach(() => {
  push.mockReset();
  api.fetchFaq.mockReset().mockResolvedValue(row);
  api.updateFaq.mockReset().mockResolvedValue({ ...row, question: "更新質問", version: 3, updated_at: "2026-08-19T02:00:00Z" });
  classificationApi.fetchFaqClassifications.mockReset().mockResolvedValue(types);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function renderLoaded() {
  render(<FaqEditPage />);
  await screen.findByDisplayValue("申請期限は？");
}

describe("CB-210 FAQ edit", () => {
  it("読み込み中を表示してからFAQ詳細・現在値・Header／Sidebarを初期表示する", async () => {
    render(<FaqEditPage />);
    expect(screen.getByText("読み込み中...")).not.toBeNull();
    await screen.findByDisplayValue("申請期限は？");
    expect(screen.getByText("1")).not.toBeNull();
    expect((screen.getByLabelText("回答") as HTMLTextAreaElement).value).toBe("8月末です。\n期限厳守です。");
    const similar = screen.getAllByLabelText(/類似質問\d/);
    expect((similar[0] as HTMLTextAreaElement).value).toBe("類似A");
    expect((similar[1] as HTMLTextAreaElement).value).toBe("類似B");
    expect((screen.getByLabelText("表示区分1") as HTMLSelectElement).value).toBe("10");
    expect((screen.getByLabelText("表示区分2") as HTMLSelectElement).value).toBe("");
    expect((screen.getByLabelText("表示区分4") as HTMLSelectElement).value).toBe("40");
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText("2026/08/19 10:02")).not.toBeNull();
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "チャットサイト" })).not.toBeNull();
    expect(screen.getByText("ＦＡＱ管理")).not.toBeNull();
  });

  it("FAQ_NOT_FOUNDなど初期取得失敗を共通エラー表示する", async () => {
    api.fetchFaq.mockRejectedValue(new FaqApiError("指定されたFAQが見つかりません。", 404, "FAQ_NOT_FOUND"));
    render(<FaqEditPage />);
    expect((await screen.findByRole("alert")).textContent).toContain("指定されたFAQが見つかりません。");
  });

  it("実値差分だけをdirtyとし、元へ戻すと更新disabledへ戻る", async () => {
    await renderLoaded();
    const question = screen.getByLabelText("質問");
    fireEvent.change(question, { target: { value: "変更" } });
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(question, { target: { value: row.question } });
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "類似質問を追加" }));
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
    const lastDelete = screen.getAllByRole("button", { name: "削除" }).at(-1)!;
    fireEvent.click(lastDelete);
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("類似質問の追加・変更・削除と順序をdirty対象にする", async () => {
    await renderLoaded();
    fireEvent.click(screen.getAllByRole("button", { name: "削除" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "類似質問を追加" }));
    fireEvent.change(screen.getByLabelText("類似質問2"), { target: { value: "類似A" } });
    expect((screen.getByLabelText("類似質問1") as HTMLTextAreaElement).value).toBe("類似B");
    expect((screen.getByLabelText("類似質問2") as HTMLTextAreaElement).value).toBe("類似A");
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("質問・回答・類似質問の文字数境界と空行を検証する", async () => {
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "q".repeat(501) } });
    fireEvent.blur(screen.getByLabelText("質問"));
    expect(screen.getByText("質問は500文字以内で入力してください。")).not.toBeNull();
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "q".repeat(500) } });
    fireEvent.change(screen.getByLabelText("回答"), { target: { value: "a".repeat(1001) } });
    fireEvent.blur(screen.getByLabelText("回答"));
    expect(screen.getByText("回答は1000文字以内で入力してください。")).not.toBeNull();
    fireEvent.change(screen.getByLabelText("回答"), { target: { value: "a".repeat(1000) } });
    fireEvent.change(screen.getByLabelText("類似質問1"), { target: { value: "" } });
    fireEvent.blur(screen.getByLabelText("類似質問1"));
    expect(screen.getByText("類似質問を入力してください。")).not.toBeNull();
    expect((screen.getByRole("button", { name: "更新する" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("全属性・区分変更／解除・Toggle・versionをPUTして一覧へ戻る", async () => {
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: " 更新質問 " } });
    fireEvent.change(screen.getByLabelText("回答"), { target: { value: " 更新回答\n本文 " } });
    fireEvent.change(screen.getByLabelText("類似質問1"), { target: { value: " 更新類似 " } });
    fireEvent.change(screen.getByLabelText("表示区分1"), { target: { value: "11" } });
    fireEvent.change(screen.getByLabelText("表示区分4"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("switch"));
    fireEvent.click(screen.getByRole("button", { name: "更新する" }));
    await waitFor(() => expect(api.updateFaq).toHaveBeenCalledWith(1, expect.objectContaining({
      question: "更新質問", answer: "更新回答\n本文", similar_questions: ["更新類似", "類似B"],
      classification_1_value_id: 11, classification_2_value_id: null,
      classification_4_value_id: null, chat_enabled: true, version: 2,
    })));
    expect(push).toHaveBeenCalledWith("/faqs");
  });

  it("更新中は入力・二重送信・離脱を無効化する", async () => {
    let resolveUpdate: ((value: FaqDetail) => void) | undefined;
    api.updateFaq.mockReturnValue(new Promise((resolve) => { resolveUpdate = resolve; }));
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "変更" } });
    fireEvent.click(screen.getByRole("button", { name: "更新する" }));
    expect(await screen.findByRole("button", { name: "更新中..." })).not.toBeNull();
    expect((screen.getByLabelText("質問") as HTMLTextAreaElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "キャンセル" }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "更新中..." }));
    expect(api.updateFaq).toHaveBeenCalledOnce();
    resolveUpdate?.({ ...row, question: "変更", version: 3 });
    await waitFor(() => expect(push).toHaveBeenCalledWith("/faqs"));
  });

  it("409競合・API validation・一般更新失敗を表示する", async () => {
    for (const [failure, message] of ([
      [new FaqApiError("競合", 409, "FAQ_VERSION_CONFLICT"), "他の操作で情報が更新されています。再読み込みしてください。"],
      [new FaqApiError("質問を入力してください。", 422, "FAQ_QUESTION_REQUIRED"), "質問を入力してください。"],
      [new FaqApiError("FAQの更新に失敗しました。", 500, "FAQ_UPDATE_FAILED"), "FAQの更新に失敗しました。"],
    ] as const)) {
      api.updateFaq.mockRejectedValueOnce(failure);
      await renderLoaded();
      fireEvent.change(screen.getByLabelText("質問"), { target: { value: "変更" } });
      fireEvent.click(screen.getByRole("button", { name: "更新する" }));
      expect(await screen.findByText(message)).not.toBeNull();
      cleanup();
    }
  });

  it("dirty時の一覧・キャンセル・Sidebar離脱をModalで確認する", async () => {
    await renderLoaded();
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "変更" } });
    fireEvent.click(screen.getByRole("button", { name: "FAQ一覧へ戻る" }));
    expect(screen.getByText("FAQを更新せずにFAQ一覧に戻ります。よろしいですか？")).not.toBeNull();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "キャンセル" }));
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(screen.getByRole("dialog")).not.toBeNull();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "キャンセル" }));
    fireEvent.click(screen.getByRole("button", { name: "データソース管理" }));
    expect(screen.getByText("入力内容を保存せずに移動します。よろしいですか？")).not.toBeNull();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "移動する" }));
    expect(push).toHaveBeenCalledWith("/data-sources");
  });

  it("dirty時だけbeforeunloadを抑止する", async () => {
    await renderLoaded();
    const cleanEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(cleanEvent);
    expect(cleanEvent.defaultPrevented).toBe(false);
    fireEvent.change(screen.getByLabelText("回答"), { target: { value: "変更" } });
    const dirtyEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(dirtyEvent);
    expect(dirtyEvent.defaultPrevented).toBe(true);
  });
});
