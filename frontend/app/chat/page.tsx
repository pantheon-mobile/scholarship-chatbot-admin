"use client";

import { CSSProperties, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AdminIcon, Modal } from "@/components/admin";
import { useAuth } from "@/components/auth/AuthProvider";
import { completeTrackedInteraction, deleteChatHistory, fetchChatConfig, fetchChatHistory, fetchChatHistoryDetail, recordChatAccess, sendChatMessage, startTrackedChat, startTrackedInteraction, submitFeedback, updateChatHistoryTitle } from "@/lib/chatApi";
import { ChatHistorySummary, ChatMessage, ChatUiConfig } from "@/types/chat";
import { MarkdownAnswer } from "./MarkdownAnswer";
import styles from "./page.module.css";

const fallbackConfig: ChatUiConfig = {
  title: "東京理科大学奨学金問合せチャット", initial_message: "奨学金について知りたいことを入力してください。登録されている資料をもとに回答します。",
  input_placeholder: "奨学金について質問を入力してください", question_max_length: 2000, frame_color: "#171a1d", bot_icon_url: null,
  history_enabled: true, maintenance_enabled: false, maintenance_message: "現在メンテナンス中です。時間をおいて再度お試しください。",
  good_message: "ご評価ありがとうございます。よろしければ理由をお聞かせください。", bad_message: "改善のため、回答が役に立たなかった理由をお聞かせください。",
  good_options: ["知りたい内容だった", "分かりやすかった", "参照資料が役立った"], bad_options: ["回答が違う", "情報が不足している", "分かりにくい", "参照資料が適切でない"],
};
type FeedbackState = { messageId: string; interactionId: string; rating: "GOOD" | "BAD" };
type EditingHistory = { id: string; title: string };
const now = () => new Date().toISOString();
function formatTimestamp(value: string) {
  const date = new Date(value); const sameDay = date.toDateString() === new Date().toDateString();
  return new Intl.DateTimeFormat("ja-JP", sameDay ? { hour: "2-digit", minute: "2-digit" } : { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}

export default function ChatPage() {
  const router = useRouter(); const { user, logout } = useAuth();
  const [config, setConfig] = useState(fallbackConfig); const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [histories, setHistories] = useState<ChatHistorySummary[]>([]); const [historyPanelOpen, setHistoryPanelOpen] = useState(false); const [historySearch, setHistorySearch] = useState("");
  const [historyMenuId, setHistoryMenuId] = useState<string>(); const [editingHistory, setEditingHistory] = useState<EditingHistory>(); const [deleteHistoryTarget, setDeleteHistoryTarget] = useState<ChatHistorySummary>();
  const [sidebarOpen, setSidebarOpen] = useState(true); const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false); const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [question, setQuestion] = useState(""); const [busy, setBusy] = useState(false); const [historyBusy, setHistoryBusy] = useState(false); const [historyActionBusy, setHistoryActionBusy] = useState(false); const [historyActionError, setHistoryActionError] = useState(""); const [error, setError] = useState("");
  const [copiedId, setCopiedId] = useState<string>(); const [feedback, setFeedback] = useState<FeedbackState>(); const [feedbackOption, setFeedbackOption] = useState("");
  const [feedbackComment, setFeedbackComment] = useState(""); const [feedbackBusy, setFeedbackBusy] = useState(false); const [feedbackError, setFeedbackError] = useState("");
  const [bedrockSessionId, setBedrockSessionId] = useState<string>(); const chatSessionId = useRef(crypto.randomUUID()); const chatStarted = useRef(false); const endRef = useRef<HTMLDivElement>(null);
  const identifier = user ? `${user.site}:${user.subject}` : "";
  const options = useMemo(() => feedback?.rating === "GOOD" ? config.good_options : config.bad_options, [config, feedback]);

  const reloadHistory = useCallback(async (search = "") => { if (config.history_enabled) try { setHistoryBusy(true); setHistories(await fetchChatHistory(search)); } catch { /* チャット自体は継続 */ } finally { setHistoryBusy(false); } }, [config.history_enabled]);
  useEffect(() => { if (!identifier) return; void recordChatAccess(crypto.randomUUID(), identifier, now()).catch(() => undefined); void fetchChatConfig().then(setConfig).catch(() => undefined); }, [identifier]);
  useEffect(() => { if (identifier) void reloadHistory(); }, [identifier, reloadHistory]);
  useEffect(() => { if (!identifier || !historyPanelOpen) return; const timer = window.setTimeout(() => void reloadHistory(historySearch), 250); return () => window.clearTimeout(timer); }, [historySearch, historyPanelOpen, identifier, reloadHistory]);
  useEffect(() => { endRef.current?.scrollIntoView?.({ behavior: "smooth" }); }, [messages, busy]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault(); const normalized = question.trim(); if (!normalized || busy || !identifier || config.maintenance_enabled) return;
    setQuestion(""); setError(""); setBusy(true); const submittedAt = now(); const interactionId = crypto.randomUUID(); const sequence = messages.filter((item) => item.role === "user").length + 1;
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: normalized, sentAt: submittedAt }]);
    try {
      if (!chatStarted.current) { await startTrackedChat(chatSessionId.current, identifier, submittedAt); chatStarted.current = true; }
      await startTrackedInteraction(chatSessionId.current, interactionId, sequence, submittedAt, normalized);
      const result = await sendChatMessage(normalized, bedrockSessionId); const answeredAt = now(); setBedrockSessionId(result.bedrock_session_id || undefined);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: result.answer, sentAt: answeredAt, citations: result.citations, interactionId, answerType: result.answer_type }]);
      await completeTrackedInteraction(interactionId, result.answer_type, answeredAt, result.answer, result.citations); await reloadHistory();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "回答を取得できませんでした。"); await completeTrackedInteraction(interactionId, null).catch(() => undefined); }
    finally { setBusy(false); }
  }
  function openFeedback(messageId: string, interactionId: string, rating: "GOOD" | "BAD") { setFeedback({ messageId, interactionId, rating }); setFeedbackOption(""); setFeedbackComment(""); setFeedbackError(""); }
  async function saveFeedback() {
    if (!feedback) return; setFeedbackBusy(true); setFeedbackError(""); const comment = [feedbackOption, feedbackComment.trim()].filter(Boolean).join("：");
    try { await submitFeedback(feedback.interactionId, feedback.rating, comment); setMessages((current) => current.map((item) => item.id === feedback.messageId ? { ...item, rating: feedback.rating } : item)); setFeedback(undefined); }
    catch (reason) { setFeedbackError(reason instanceof Error ? reason.message : "評価を保存できませんでした。"); } finally { setFeedbackBusy(false); }
  }
  function newChat() { chatSessionId.current = crypto.randomUUID(); chatStarted.current = false; setBedrockSessionId(undefined); setMessages([]); setError(""); setMobileSidebarOpen(false); }
  function toggleSidebar() {
    if (window.matchMedia("(max-width: 760px)").matches) setMobileSidebarOpen((value) => !value);
    else setSidebarOpen((value) => !value);
  }
  async function openHistory(id: string) {
    setHistoryBusy(true); setError(""); try { const detail = await fetchChatHistoryDetail(id); chatSessionId.current = id; chatStarted.current = true; setBedrockSessionId(undefined); setMessages(detail.messages.map((item) => ({ id: item.id, role: item.role, content: item.content, sentAt: item.sent_at, citations: item.citations, interactionId: item.interaction_id || undefined, rating: item.rating || undefined, answerType: item.answer_type || undefined }))); setMobileSidebarOpen(false); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "履歴を取得できませんでした。"); } finally { setHistoryBusy(false); }
  }
  async function saveHistoryTitle() {
    if (!editingHistory || historyActionBusy) return; const title = editingHistory.title.trim(); if (!title) { setError("チャット名を入力してください。"); return; }
    setHistoryActionBusy(true); setError(""); try { const updated = await updateChatHistoryTitle(editingHistory.id, title); setHistories((current) => current.map((item) => item.id === updated.id ? updated : item)); setEditingHistory(undefined); setHistoryMenuId(undefined); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "チャット名を変更できませんでした。"); } finally { setHistoryActionBusy(false); }
  }
  async function confirmDeleteHistory() {
    if (!deleteHistoryTarget || historyActionBusy) return; const id = deleteHistoryTarget.id; setHistoryActionBusy(true); setHistoryActionError("");
    try { await deleteChatHistory(id); setHistories((current) => current.filter((item) => item.id !== id)); setDeleteHistoryTarget(undefined); setHistoryMenuId(undefined); if (chatSessionId.current === id) newChat(); }
    catch (reason) { setHistoryActionError(reason instanceof Error ? reason.message : "チャットを削除できませんでした。"); } finally { setHistoryActionBusy(false); }
  }
  async function copyAnswer(message: ChatMessage) { try { await navigator.clipboard.writeText(message.content); setCopiedId(message.id); window.setTimeout(() => setCopiedId(undefined), 1500); } catch { setError("回答をコピーできませんでした。"); } }

  return <main className={styles.main} style={{ "--chat-frame-color": config.frame_color } as CSSProperties}>
    <header className={styles.header}><div className={styles.brand}><span className={styles.schoolIcon}><AdminIcon name="university" size={32} /></span><h1>{config.title}</h1></div><button type="button" className={styles.adminLink} onClick={() => router.push("/")}>管理サイト</button><div className={styles.userWrap}><button type="button" className={styles.userButton} onClick={() => setUserMenuOpen((value) => !value)}>{user?.display_name || user?.subject} ▾</button>{userMenuOpen && <div className={styles.userMenu}><span>ID：{user?.subject}</span><button type="button" onClick={() => setUserMenuOpen(false)}>閉じる</button><button type="button" onClick={() => void logout()}>ログアウト</button></div>}</div></header>
    {mobileSidebarOpen && <button className={styles.scrim} aria-label="メニューを閉じる" onClick={() => setMobileSidebarOpen(false)} />}
    <aside className={`${styles.sidebar} ${sidebarOpen ? "" : styles.sidebarCollapsed} ${mobileSidebarOpen ? styles.sidebarMobileOpen : ""}`}><button type="button" className={styles.sidebarMenuTrigger} aria-label={sidebarOpen ? "サイドメニューを閉じる" : "サイドメニューを開く"} aria-expanded={sidebarOpen} onClick={toggleSidebar}><AdminIcon name="menu" size={34} /></button><div className={styles.sidebarBody}><button type="button" className={styles.newChat} onClick={newChat}><span className={styles.sidebarIcon}><AdminIcon name="plus" size={30} /></span><b>新しいチャット</b></button>{config.history_enabled && <><button type="button" className={`${styles.historyToggle} ${historyPanelOpen ? styles.historyToggleActive : ""}`} aria-expanded={historyPanelOpen} onClick={() => { setHistoryPanelOpen(true); setHistoryMenuId(undefined); setEditingHistory(undefined); }}><span className={styles.sidebarIcon}><AdminIcon name="chat" size={30} /></span><b>チャット履歴</b></button><div className={styles.historyPanel}>{historyPanelOpen && <label className={styles.historySearch}><button type="button" className={styles.historySearchBack} aria-label="検索を終了" onClick={() => { setHistoryPanelOpen(false); setHistorySearch(""); setHistoryMenuId(undefined); setEditingHistory(undefined); void reloadHistory(""); }}><AdminIcon name="back" size={20} /></button><span className={styles.visuallyHidden}>チャットを検索</span><input autoFocus value={historySearch} placeholder="チャットを検索" onChange={(event) => setHistorySearch(event.target.value)} /></label>}<div className={styles.recent}><h2>{historyPanelOpen ? (historySearch.trim() ? "検索結果" : "チャット履歴") : "最近の履歴"}</h2>{historyBusy && <p>読み込み中…</p>}{!historyBusy && histories.map((item) => <div className={styles.historyRow} key={item.id}>{editingHistory?.id === item.id ? <div className={styles.historyEdit}><input aria-label="チャット名" maxLength={100} value={editingHistory.title} disabled={historyActionBusy} onChange={(event) => setEditingHistory({ ...editingHistory, title: event.target.value })} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); void saveHistoryTitle(); } if (event.key === "Escape") setEditingHistory(undefined); }} /><button type="button" onClick={() => setEditingHistory(undefined)}>キャンセル</button></div> : <><button type="button" className={styles.historyOpen} title={item.title} onClick={() => void openHistory(item.id)}><span>{item.title}</span></button><button type="button" className={styles.historyMore} aria-label={`${item.title}のメニュー`} aria-expanded={historyMenuId === item.id} onClick={() => setHistoryMenuId((value) => value === item.id ? undefined : item.id)}>⋮</button>{historyMenuId === item.id && <div className={styles.historyActions}><button type="button" onClick={() => { setEditingHistory({ id: item.id, title: item.title }); setHistoryMenuId(undefined); }}>編集</button><button type="button" className={styles.historyDelete} onClick={() => { setDeleteHistoryTarget(item); setHistoryMenuId(undefined); }}>削除</button></div>}</>}</div>)}{!historyBusy && histories.length === 0 && <p>{historyPanelOpen && historySearch.trim() ? "該当するチャットはありません" : "履歴はありません"}</p>}</div></div></>}</div></aside>
    <section className={`${styles.chat} ${sidebarOpen ? "" : styles.chatExpanded}`} aria-label="チャット"><div className={styles.messages} aria-live="polite">{config.maintenance_enabled && <div className={styles.maintenance}>{config.maintenance_message}</div>}{messages.map((message) => <article key={message.id} className={`${styles.messageRow} ${message.role === "user" ? styles.userRow : styles.assistantRow}`}><div className={`${styles.message} ${message.role === "user" ? styles.userMessage : styles.assistantMessage}`}><div className={styles.role}>{message.role === "user" ? "あなた" : "チャットボット"}</div>{message.role === "assistant" ? <MarkdownAnswer content={message.content} /> : <p>{message.content}</p>}{!!message.citations?.length && <div className={styles.citations}><b>参照資料</b><ul>{message.citations.map((citation, index) => <li key={`${citation.title}-${index}`}>{citation.uri ? <a href={citation.uri} target="_blank" rel="noopener noreferrer">{citation.title}</a> : citation.title}</li>)}</ul></div>}<time dateTime={message.sentAt}>{formatTimestamp(message.sentAt)}</time>{message.interactionId && <div className={styles.feedback}><span>回答は役に立ちましたか？</span><button className={message.rating === "GOOD" ? styles.selected : ""} onClick={() => openFeedback(message.id, message.interactionId!, "GOOD")}>Good</button><button className={message.rating === "BAD" ? styles.selected : ""} onClick={() => openFeedback(message.id, message.interactionId!, "BAD")}>Bad</button><button className={styles.copy} onClick={() => void copyAnswer(message)} aria-label="回答をコピー">{copiedId === message.id ? "コピー済み" : "コピー"}</button></div>}</div></article>)}{busy && <article className={`${styles.messageRow} ${styles.assistantRow}`}><div className={`${styles.message} ${styles.assistantMessage}`}><div className={styles.role}>チャットボット</div><p className={styles.thinking}>回答を作成しています<span>…</span></p></div></article>}<div ref={endRef} /></div>
      {error && <p className={styles.error} role="alert">{error}</p>}<form className={styles.composer} onSubmit={handleSubmit}><label htmlFor="chat-question" className={styles.visuallyHidden}>質問</label><textarea id="chat-question" value={question} maxLength={config.question_max_length} rows={1} placeholder={config.input_placeholder} disabled={busy || config.maintenance_enabled} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} /><button type="submit" disabled={busy || !question.trim() || config.maintenance_enabled}>送信</button></form><p className={styles.notice}>生成AIの回答には誤りが含まれる場合があります。重要な手続きは参照資料や担当窓口でもご確認ください。</p></section>
    <Modal open={Boolean(feedback)} title={feedback?.rating === "GOOD" ? "回答へのGood評価" : "回答へのBad評価"} confirmLabel={feedbackBusy ? "保存中…" : "送信する"} busy={feedbackBusy} error={feedbackError || undefined} onConfirm={() => void saveFeedback()} onClose={() => setFeedback(undefined)}><div className={styles.feedbackForm}><p>{feedback?.rating === "GOOD" ? config.good_message : config.bad_message}</p><label>理由（任意）<select value={feedbackOption} onChange={(event) => setFeedbackOption(event.target.value)}><option value="">選択してください</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</select></label><label>コメント（任意）<textarea maxLength={1000} rows={4} value={feedbackComment} onChange={(event) => setFeedbackComment(event.target.value)} /></label></div></Modal>
    <Modal open={Boolean(deleteHistoryTarget)} title="チャットの削除" variant="danger" confirmLabel={historyActionBusy ? "削除中…" : "削除"} busy={historyActionBusy} error={historyActionError || undefined} onConfirm={() => void confirmDeleteHistory()} onClose={() => { if (!historyActionBusy) { setDeleteHistoryTarget(undefined); setHistoryActionError(""); } }}><p>このチャットを削除しますか？<br />このチャットに戻ることはできなくなります。</p></Modal>
  </main>;
}
