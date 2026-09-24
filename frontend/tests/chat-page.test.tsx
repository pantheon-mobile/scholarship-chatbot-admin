import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  completeTrackedInteraction: vi.fn(), deleteChatHistory: vi.fn(), fetchChatConfig: vi.fn(), fetchChatHistory: vi.fn(),
  fetchChatHistoryDetail: vi.fn(), recordChatAccess: vi.fn(), sendChatMessage: vi.fn(),
  startTrackedChat: vi.fn(), startTrackedInteraction: vi.fn(), submitFeedback: vi.fn(), updateChatHistoryTitle: vi.fn(),
}));
const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../components/auth/AuthProvider", () => ({
  useAuth: () => ({ user: { subject: "staff-001", display_name: "開発 職員", role: "staff", site: "faculty" }, logout: vi.fn() }),
}));
vi.mock("../lib/chatApi", () => api);

import ChatPage from "../app/chat/page";

beforeEach(() => {
  router.push.mockReset();
  Object.values(api).forEach((mock) => mock.mockReset());
  api.fetchChatConfig.mockResolvedValue({
    title: "試験チャット", admin_title: "試験管理サイト", header_icon_url: null,
    initial_message: "最初の案内", input_placeholder: "質問を入力", question_max_length: 200,
    frame_color: "#171a1d", bot_icon_url: null, history_enabled: true, maintenance_enabled: false,
    maintenance_message: "保守中", good_message: "Good理由", bad_message: "Bad理由",
    good_options: ["分かりやすい"], bad_options: ["回答が違う"],
  });
  api.fetchChatHistory.mockResolvedValue([{ id: "11111111-1111-4111-8111-111111111111", title: "過去の質問", started_at: "2026-09-03T00:00:00Z", updated_at: "2026-09-03T00:01:00Z" }]);
  api.updateChatHistoryTitle.mockResolvedValue({ id: "11111111-1111-4111-8111-111111111111", title: "変更後の名前", started_at: "2026-09-03T00:00:00Z", updated_at: "2026-09-03T00:01:00Z" });
  api.deleteChatHistory.mockResolvedValue(undefined);
  api.sendChatMessage.mockResolvedValue({ answer: "回答です", answer_type: "GENERATED_AI", bedrock_session_id: "bedrock-1", citations: [] });
  api.recordChatAccess.mockResolvedValue(undefined); api.startTrackedChat.mockResolvedValue(undefined); api.startTrackedInteraction.mockResolvedValue(undefined); api.completeTrackedInteraction.mockResolvedValue(undefined); api.submitFeedback.mockResolvedValue(undefined);
});

afterEach(cleanup);

describe("CB-101 チャットUI", () => {
  it("日本語変換を確定するEnterでは送信しない", async () => {
    render(<ChatPage />);
    const input = screen.getByLabelText("質問");
    fireEvent.change(input, { target: { value: "給付奨学金" } });
    fireEvent.compositionStart(input);
    fireEvent.keyDown(input, { key: "Enter", keyCode: 229, isComposing: true });
    expect(api.sendChatMessage).not.toHaveBeenCalled();
    expect((input as HTMLTextAreaElement).value).toBe("給付奨学金");

    fireEvent.compositionEnd(input);
    fireEvent.keyDown(input, { key: "Enter", keyCode: 13, isComposing: false });
    await waitFor(() => expect(api.sendChatMessage).toHaveBeenCalledWith("給付奨学金", expect.any(String), expect.any(String)));
  });

  it("左メニュー、履歴、日時を表示し、Good理由をポップアップからDB APIへ送る", async () => {
    render(<ChatPage />);
    expect(screen.getByRole("button", { name: "サイドメニューを閉じる" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /新しいチャット/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /チャット履歴/ })).toBeTruthy();
    await screen.findByText("過去の質問");

    fireEvent.change(screen.getByLabelText("質問"), { target: { value: "申請期限は？" } });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));
    await screen.findByText("回答です");
    expect(screen.getAllByRole("time").length).toBeGreaterThanOrEqual(2);

    fireEvent.click(screen.getByRole("button", { name: "Good" }));
    expect(screen.getByRole("dialog", { name: "回答へのGood評価" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("理由（任意）"), { target: { value: "分かりやすい" } });
    fireEvent.change(screen.getByLabelText("コメント（任意）"), { target: { value: "助かりました" } });
    fireEvent.click(screen.getByRole("button", { name: "送信する" }));
    await waitFor(() => expect(api.submitFeedback).toHaveBeenCalledWith(expect.any(String), "GOOD", "助かりました", "分かりやすい"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Good" }).getAttribute("aria-pressed")).toBe("true"));
    expect(screen.getByRole("button", { name: "Bad" }).getAttribute("aria-pressed")).toBe("false");
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    fireEvent.click(screen.getByRole("button", { name: "回答をコピー" }));
    await screen.findByText("コピー済み");
    expect(writeText).toHaveBeenCalledWith("回答です");
  });

  it("利用者名ボタンからIDと操作メニューを表示し、閉じるで管理画面へ戻る", () => {
    render(<ChatPage />);
    expect(screen.queryByRole("button", { name: "ログアウト" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "開発 職員 ▾" }));
    expect(screen.getByText("ID：staff-001")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "閉じる" }));
    expect(router.push).toHaveBeenCalledWith("/");
    expect(screen.queryByRole("button", { name: "ログアウト" })).toBeNull();
  });

  it("新規チャットでは案内メッセージ枠を表示しない", async () => {
    render(<ChatPage />);
    await waitFor(() => expect(api.fetchChatConfig).toHaveBeenCalled());
    expect(screen.queryByText("最初の案内")).toBeNull();
    expect(screen.queryByText("チャットボット")).toBeNull();
  });

  it("質問・回答本文を検索し、チャット名をEnterで保存またはキャンセルできる", async () => {
    render(<ChatPage />);
    await screen.findByText("過去の質問");
    expect(screen.queryByPlaceholderText("チャットを検索")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /チャット履歴/ }));
    const search = await screen.findByPlaceholderText("チャットを検索");
    fireEvent.change(search, { target: { value: "予約採用" } });
    await waitFor(() => expect(api.fetchChatHistory).toHaveBeenCalledWith("予約採用"));

    fireEvent.click(screen.getByRole("button", { name: "過去の質問のメニュー" }));
    fireEvent.click(screen.getByRole("button", { name: "編集" }));
    const title = screen.getByLabelText("チャット名");
    fireEvent.change(title, { target: { value: "変更後の名前" } });
    fireEvent.keyDown(title, { key: "Enter" });
    await waitFor(() => expect(api.updateChatHistoryTitle).toHaveBeenCalledWith("11111111-1111-4111-8111-111111111111", "変更後の名前"));
    await screen.findByText("変更後の名前");

    fireEvent.click(screen.getByRole("button", { name: "変更後の名前のメニュー" }));
    fireEvent.click(screen.getByRole("button", { name: "編集" }));
    fireEvent.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(screen.queryByLabelText("チャット名")).toBeNull();
  });

  it("戻るアイコンで検索モードを終了して通常の履歴表示へ戻る", async () => {
    render(<ChatPage />);
    await screen.findByText("過去の質問");
    fireEvent.click(screen.getByRole("button", { name: /チャット履歴/ }));
    fireEvent.change(screen.getByPlaceholderText("チャットを検索"), { target: { value: "進学届" } });
    fireEvent.click(screen.getByRole("button", { name: "検索を終了" }));
    expect(screen.queryByPlaceholderText("チャットを検索")).toBeNull();
    expect(screen.getByText("最近の履歴")).toBeTruthy();
    await waitFor(() => expect(api.fetchChatHistory).toHaveBeenCalledWith(""));
  });

  it("共通ダイアログで削除確認し履歴を削除する", async () => {
    render(<ChatPage />);
    fireEvent.click(screen.getByRole("button", { name: /チャット履歴/ }));
    await screen.findByText("過去の質問");
    fireEvent.click(screen.getByRole("button", { name: "過去の質問のメニュー" }));
    fireEvent.click(screen.getByRole("button", { name: "削除" }));
    const dialog = screen.getByRole("dialog", { name: "チャットの削除" });
    expect(dialog.textContent).toContain("このチャットを削除しますか？");
    expect(dialog.textContent).toContain("このチャットに戻ることはできなくなります。");
    fireEvent.click(screen.getByRole("button", { name: /^削除$/ }));
    await waitFor(() => expect(api.deleteChatHistory).toHaveBeenCalledWith("11111111-1111-4111-8111-111111111111"));
  });
});

it("生成AI回答の参照元タイトルを複数行のリンクとして表示する", async () => {
  const citations = [
    { title: "第一種奨学金の返還案内", uri: "/api/v1/chat/sources/7/download" },
    { title: "返還方式の説明", uri: "https://example.com/repayment" },
  ];
  api.sendChatMessage.mockResolvedValue({ answer: "定額返還方式と所得連動返還方式です。", answer_type: "GENERATED_AI", citations });
  render(<ChatPage />);
  fireEvent.change(screen.getByLabelText("質問"), { target: { value: "第一種奨学金の返還方式は？" } });
  fireEvent.keyDown(screen.getByLabelText("質問"), { key: "Enter", keyCode: 13 });
  expect(await screen.findByText("【参照元】")).toBeTruthy();
  expect(screen.getByRole("link", { name: citations[0].title }).getAttribute("href")).toBe("/api/v1/chat/sources/7/download");
  expect(screen.getByRole("link", { name: citations[1].title }).getAttribute("href")).toBe(citations[1].uri);
  expect(screen.getByRole("link", { name: citations[0].title }).closest("li")).not.toBe(screen.getByRole("link", { name: citations[1].title }).closest("li"));
});

it.each(["NO_ANSWER", "GENERATED_AI"])("%sの分類に従って案内回答の参照元を制御する", async (answerType) => {
  const answer = "ご質問の内容が具体的に記載されていないため、お答えすることができません。例えば、奨学金の採用基準や手続きについてお答えできます。";
  api.sendChatMessage.mockResolvedValue({ answer, answer_type: answerType, citations: [{ title: "奨学金事務マニュアル", uri: "/api/v1/chat/sources/7/download" }] });
  render(<ChatPage />);
  fireEvent.change(screen.getByLabelText("質問"), { target: { value: "クエスチョンがあるよ" } });
  fireEvent.click(screen.getByRole("button", { name: "送信" }));
  await screen.findByText(answer);
  expect(Boolean(screen.queryByText("【参照元】"))).toBe(answerType !== "NO_ANSWER");
  expect(Boolean(screen.queryByRole("link", { name: "奨学金事務マニュアル" }))).toBe(answerType !== "NO_ANSWER");
});

it("3件目以降もチャット欄だけをスクロールし、評価保存では動かさない", async () => {
  render(<ChatPage />);
  await screen.findByRole("heading", { name: "試験チャット" });
  const container = screen.getByRole("region", { name: "チャット" }).querySelector('[aria-live="polite"]') as HTMLElement;
  const scrollTo = vi.fn();
  Object.defineProperty(container, "scrollTo", { value: scrollTo, configurable: true });
  Object.defineProperty(container, "scrollHeight", { value: 1600, configurable: true });
  for (let index = 1; index <= 4; index++) {
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: `質問${index}` } });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Good" })).toHaveLength(index));
    await waitFor(() => expect((screen.getByLabelText("質問") as HTMLTextAreaElement).disabled).toBe(false));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 1600, behavior: "smooth" });
  }
  for (const rating of ["Good", "Bad"]) {
    scrollTo.mockClear();
    fireEvent.click(screen.getAllByRole("button", { name: rating })[0]);
    fireEvent.change(screen.getByLabelText("コメント（任意）"), { target: { value: "確認コメント" } });
    fireEvent.click(screen.getByRole("button", { name: "送信する" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(scrollTo).not.toHaveBeenCalled();
  }
});

it("FAQを挟んでも同じチャットIDを送信し、新しいチャットでは切り替える", async () => {
  api.sendChatMessage.mockResolvedValueOnce({ answer: "FAQの説明", answer_type: "FAQ", citations: [] })
    .mockResolvedValue({ answer: "続きの説明", answer_type: "GENERATED_AI", citations: [] });
  render(<ChatPage />);
  async function ask(text: string, count: number) {
    fireEvent.change(screen.getByLabelText("質問"), { target: { value: text } });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));
    await waitFor(() => expect(api.completeTrackedInteraction).toHaveBeenCalledTimes(count));
    await waitFor(() => expect((screen.getByRole("button", { name: /新しいチャット/ }) as HTMLButtonElement).disabled).toBe(false));
  }
  await ask("第一種奨学金の返還方式", 1);
  const firstId = api.sendChatMessage.mock.calls[0][1];
  await ask("後者の条件は？", 2);
  expect(api.sendChatMessage.mock.calls[1]).toEqual(["後者の条件は？", firstId, expect.any(String)]);
  fireEvent.click(screen.getByRole("button", { name: /新しいチャット/ }));
  await ask("昨日の件", 3);
  expect(api.sendChatMessage.mock.calls[2][1]).not.toBe(firstId);
});

it("履歴の続きを送る際に元のチャットIDと失敗分を含む次の連番を使用する", async () => {
  const id = "11111111-1111-4111-8111-111111111111";
  api.fetchChatHistoryDetail.mockResolvedValue({ id, title: "過去の質問", next_sequence_number: 4, messages: [
    { id: "q", role: "user", content: "第一種の返還方式", sent_at: "2026-09-17T00:00:00Z", citations: [] },
    { id: "a", role: "assistant", content: "定額と所得連動です", sent_at: "2026-09-17T00:00:01Z", citations: [], answer_type: "FAQ" },
  ] });
  render(<ChatPage />);
  fireEvent.click(await screen.findByRole("button", { name: "過去の質問" }));
  await screen.findByText("定額と所得連動です");
  fireEvent.change(screen.getByLabelText("質問"), { target: { value: "後者の条件は？" } });
  fireEvent.click(screen.getByRole("button", { name: "送信" }));
  await waitFor(() => expect(api.sendChatMessage).toHaveBeenCalledWith("後者の条件は？", id, expect.any(String)));
  expect(api.startTrackedInteraction).toHaveBeenCalledWith(id, expect.any(String), 4, expect.any(String), "後者の条件は？");
  expect(api.startTrackedChat).not.toHaveBeenCalled();
});

it("別チャット参照の切り替えUIはなく、参照した場合はチャット名を表示する", async () => {
  api.sendChatMessage.mockResolvedValue({ answer: "現在の資料の回答", answer_type: "GENERATED_AI", citations: [], context_reference: "第一種の相談" });
  render(<ChatPage />);
  expect(screen.queryByRole("checkbox", { name: "別のチャットの履歴も参照" })).toBeNull();
  fireEvent.change(screen.getByLabelText("質問"), { target: { value: "昨日の件" } });
  fireEvent.click(screen.getByRole("button", { name: "送信" }));
  await waitFor(() => expect(api.sendChatMessage).toHaveBeenCalledWith("昨日の件", expect.any(String), expect.any(String)));
  expect(await screen.findByText("過去のチャット「第一種の相談」を参照しています。")).toBeTruthy();
});

it.each([['Good', 'GOOD'], ['Bad', 'BAD']])('回答NGでも%s評価とコメントを送信できる', async (label, rating) => {
  api.sendChatMessage.mockResolvedValue({ answer: '登録情報から確認できませんでした。', answer_type: 'NO_ANSWER', citations: [] });
  render(<ChatPage />);
  fireEvent.change(screen.getByLabelText('質問'), { target: { value: '申請期限は？' } });
  fireEvent.click(screen.getByRole('button', { name: '送信' }));
  await screen.findByText('登録情報から確認できませんでした。');
  fireEvent.click(screen.getByRole('button', { name: label }));
  fireEvent.change(screen.getByLabelText('コメント（任意）'), { target: { value: '回答できない質問ではないはずです' } });
  fireEvent.click(screen.getByRole('button', { name: '送信する' }));
  await waitFor(() => expect(api.submitFeedback).toHaveBeenCalledWith(expect.any(String), rating, '回答できない質問ではないはずです', ''));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(screen.getByRole('button', { name: label }).getAttribute('aria-pressed')).toBe('true');
});


it.each(["Failed to fetch", "NetworkError when attempting to fetch resource.", "Load failed"])("通信失敗 %s の案内後に同じ画面で再送信できる", async (message) => {
  api.sendChatMessage.mockRejectedValueOnce(new TypeError(message));
  render(<ChatPage />);
  fireEvent.change(screen.getByLabelText("質問"), { target: { value: "申請期限は？" } });
  fireEvent.click(screen.getByRole("button", { name: "送信" }));
  const notice = "接続エラーにより、回答を取得できませんでした。インターネット接続を確認し、時間をおいてもう一度質問を送信してください。解消しない場合は、システム管理者にお問い合わせください。";
  await screen.findByText(notice);
  await waitFor(() => expect((screen.getByLabelText("質問") as HTMLTextAreaElement).disabled).toBe(false));
  expect(api.sendChatMessage).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText("質問"), { target: { value: "申請期限は？" } });
  fireEvent.click(screen.getByRole("button", { name: "送信" }));
  await screen.findByText("回答です");
  expect(api.sendChatMessage).toHaveBeenCalledTimes(2);
  expect(screen.queryByText(notice)).toBeNull();
});

it("APIが返した具体的なエラーを接続エラーに置き換えない", async () => {
  api.sendChatMessage.mockRejectedValueOnce(new Error("現在メンテナンス中です。"));
  render(<ChatPage />);
  fireEvent.change(screen.getByLabelText("質問"), { target: { value: "申請期限は？" } });
  fireEvent.click(screen.getByRole("button", { name: "送信" }));
  expect(await screen.findByText("現在メンテナンス中です。")).toBeTruthy();
});

async function openSavedFeedbackChat(rating: "GOOD" | "BAD" = "GOOD") {
  api.fetchChatHistoryDetail.mockResolvedValue({ id: "11111111-1111-4111-8111-111111111111", title: "過去の質問", messages: [
    { id: "saved-answer", role: "assistant", content: "保存済み回答", sent_at: "2026-09-03T00:01:00Z", interaction_id: "saved-interaction", rating, feedback_reason: "保存時の理由", feedback_comment: "保存したコメント", answer_type: "NO_ANSWER", citations: [] },
  ] });
  render(<ChatPage />);
  fireEvent.click(await screen.findByText("過去の質問"));
  await screen.findByText("保存済み回答");
}
const valueOf = (label: string) => (screen.getByLabelText(label) as HTMLInputElement).value;
const clickButton = (name: string) => fireEvent.click(screen.getByRole("button", { name }));
const editFeedback = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

it.each(["Good", "Bad"] as const)("履歴から%sを復元し、逆評価のキャンセルで消さない", async (label) => {
  await openSavedFeedbackChat(label === "Good" ? "GOOD" : "BAD");
  clickButton(label);
  expect(valueOf("理由（任意）")).toBe("保存時の理由");
  expect(valueOf("コメント（任意）")).toBe("保存したコメント");
  expect(screen.getByRole("option", { name: "保存時の理由" })).toBeTruthy();
  editFeedback("コメント（任意）", "未送信"); clickButton("キャンセル");
  clickButton(label === "Good" ? "Bad" : "Good");
  expect(valueOf("理由（任意）")).toBe(""); expect(valueOf("コメント（任意）")).toBe("");
  clickButton("キャンセル"); clickButton(label);
  expect(valueOf("コメント（任意）")).toBe("保存したコメント");
  expect(api.submitFeedback).not.toHaveBeenCalled();
});

it("失敗時の入力保持、再送信、GoodからBadからGoodへの置換", async () => {
  await openSavedFeedbackChat(); clickButton("Bad");
  editFeedback("理由（任意）", "回答が違う"); editFeedback("コメント（任意）", "修正してください");
  api.submitFeedback.mockRejectedValueOnce(new Error("保存失敗")); clickButton("送信する");
  await screen.findByText("保存失敗");
  expect(valueOf("コメント（任意）")).toBe("修正してください");
  expect(screen.getByRole("button", { name: "Good" }).getAttribute("aria-pressed")).toBe("true");
  clickButton("送信する"); await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  clickButton("Bad"); expect(valueOf("理由（任意）")).toBe("回答が違う"); expect(valueOf("コメント（任意）")).toBe("修正してください");
  clickButton("キャンセル"); clickButton("Good");
  expect(valueOf("理由（任意）")).toBe(""); expect(valueOf("コメント（任意）")).toBe("");
  clickButton("送信する"); await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  clickButton("Good"); expect(valueOf("コメント（任意）")).toBe("");
});

it("同じ評価で空欄送信すると保存内容を消去する", async () => {
  await openSavedFeedbackChat(); clickButton("Good");
  editFeedback("理由（任意）", ""); editFeedback("コメント（任意）", ""); clickButton("送信する");
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(api.submitFeedback).toHaveBeenCalledWith("saved-interaction", "GOOD", "", "");
  clickButton("Good"); expect(valueOf("理由（任意）")).toBe(""); expect(valueOf("コメント（任意）")).toBe("");
});
