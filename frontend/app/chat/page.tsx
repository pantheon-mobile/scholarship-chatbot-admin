"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { completeTrackedInteraction, recordChatAccess, sendChatMessage, startTrackedChat, startTrackedInteraction, submitFeedback } from "@/lib/chatApi";
import { ChatMessage } from "@/types/chat";
import styles from "./page.module.css";

const greeting: ChatMessage = { id: "greeting", role: "assistant", content: "奨学金について知りたいことを入力してください。登録されている資料をもとに回答します。" };

export default function ChatPage() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([greeting]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [bedrockSessionId, setBedrockSessionId] = useState<string>();
  const chatSessionId = useRef(crypto.randomUUID());
  const chatStarted = useRef(false);
  const endRef = useRef<HTMLDivElement>(null);
  const identifier = user ? `${user.site}:${user.subject}` : "";

  useEffect(() => { if (identifier) void recordChatAccess(crypto.randomUUID(), identifier, new Date().toISOString()).catch(() => undefined); }, [identifier]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const normalized = question.trim();
    if (!normalized || busy || !identifier) return;
    setQuestion(""); setError(""); setBusy(true);
    const submittedAt = new Date().toISOString();
    const interactionId = crypto.randomUUID();
    const sequence = messages.filter((item) => item.role === "user").length + 1;
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: normalized }]);
    try {
      if (!chatStarted.current) { await startTrackedChat(chatSessionId.current, identifier, submittedAt); chatStarted.current = true; }
      await startTrackedInteraction(chatSessionId.current, interactionId, sequence, submittedAt);
      const result = await sendChatMessage(normalized, bedrockSessionId);
      setBedrockSessionId(result.bedrock_session_id || undefined);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: result.answer, citations: result.citations, interactionId }]);
      await completeTrackedInteraction(interactionId, result.answer_type, new Date().toISOString());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "回答を取得できませんでした。");
      await completeTrackedInteraction(interactionId, null).catch(() => undefined);
    } finally { setBusy(false); }
  }

  async function rate(messageId: string, interactionId: string, rating: "GOOD" | "BAD") {
    try {
      await submitFeedback(interactionId, rating);
      setMessages((current) => current.map((item) => item.id === messageId ? { ...item, rating } : item));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "評価を保存できませんでした。"); }
  }

  function newChat() {
    chatSessionId.current = crypto.randomUUID(); chatStarted.current = false;
    setBedrockSessionId(undefined); setMessages([greeting]); setError("");
  }

  return <main className={styles.main}>
    <header className={styles.header}>
      <button type="button" className={styles.back} onClick={() => router.push("/")}>← 管理画面へ戻る</button>
      <div><span className={styles.eyebrow}>Scholarship Support</span><h1>奨学金チャットボット</h1></div>
      <div className={styles.headerActions}><span>{user?.display_name || user?.subject}</span><button type="button" onClick={() => { void logout(); }}>ログアウト</button></div>
    </header>
    <section className={styles.chat} aria-label="チャット">
      <div className={styles.toolbar}><button type="button" onClick={newChat}>新しいチャット</button></div>
      <div className={styles.messages} aria-live="polite">
        {messages.map((message) => <article key={message.id} className={`${styles.message} ${message.role === "user" ? styles.userMessage : styles.assistantMessage}`}>
          <div className={styles.role}>{message.role === "user" ? "あなた" : "チャットボット"}</div><p>{message.content}</p>
          {!!message.citations?.length && <details className={styles.citations}><summary>参照資料（{message.citations.length}件）</summary><ul>{message.citations.map((citation, index) => <li key={`${citation.title}-${index}`}>{citation.uri ? <a href={citation.uri} target="_blank" rel="noopener noreferrer">{citation.title}</a> : citation.title}</li>)}</ul></details>}
          {message.interactionId && <div className={styles.feedback}><span>回答は役に立ちましたか？</span><button className={message.rating === "GOOD" ? styles.selected : ""} onClick={() => void rate(message.id, message.interactionId!, "GOOD")}>Good</button><button className={message.rating === "BAD" ? styles.selected : ""} onClick={() => void rate(message.id, message.interactionId!, "BAD")}>Bad</button></div>}
        </article>)}
        {busy && <article className={`${styles.message} ${styles.assistantMessage}`}><div className={styles.role}>チャットボット</div><p>回答を作成しています…</p></article>}<div ref={endRef} />
      </div>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <form className={styles.composer} onSubmit={handleSubmit}>
        <label htmlFor="chat-question" className={styles.visuallyHidden}>質問</label>
        <textarea id="chat-question" value={question} maxLength={2000} rows={3} placeholder="奨学金について質問を入力してください" disabled={busy} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} />
        <button type="submit" disabled={busy || !question.trim()}>送信</button>
      </form>
      <p className={styles.notice}>生成AIの回答には誤りが含まれる場合があります。重要な手続きは参照資料や担当窓口でもご確認ください。</p>
    </section>
  </main>;
}
