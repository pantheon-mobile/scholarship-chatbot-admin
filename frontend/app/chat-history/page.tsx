"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { AdminIcon, AdminLayout, Button, FormField, PageHeader, SelectField } from "@/components/admin";
import { downloadChatHistory } from "@/lib/reportingApi";
import styles from "./page.module.css";

function initialPeriod() { const today = new Date(); const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1); const from = new Date(yesterday.getFullYear(), yesterday.getMonth(), 1); const local = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`; return { from: local(from), to: local(yesterday) }; }

export default function ChatHistoryPage() {
  const router = useRouter(); const [initial] = useState(initialPeriod);
  const [from, setFrom] = useState(initial.from); const [to, setTo] = useState(initial.to);
  const [answerType, setAnswerType] = useState(""); const [rating, setRating] = useState(""); const [comment, setComment] = useState(""); const [role, setRole] = useState(""); const [userIds, setUserIds] = useState("");
  const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  const download = async () => { setLoading(true); setError(""); try { await downloadChatHistory({ from, to, answerType, rating, comment, role, userIds }); } catch (reason) { setError(reason instanceof Error ? reason.message : "チャット履歴を取得できませんでした。"); } finally { setLoading(false); } };
  return <AdminLayout activeMenu="chat-history" contentWidth="default" contentAlign="start" onNavigate={(href) => router.push(href)}>
    <PageHeader title="チャット履歴ダウンロード" />
    {error && <p className={styles.error} role="alert">{error}</p>}
    <section className={styles.formArea}>
      <div className={styles.period}><b>期間指定：</b><FormField aria-label="From" type="date" value={from} onChange={(e) => setFrom(e.target.value)} required /><span>～</span><FormField aria-label="To" type="date" value={to} onChange={(e) => setTo(e.target.value)} required /></div>
      <SelectField label="チャット回答種別：" value={answerType} onChange={(e) => setAnswerType(e.target.value)}><option value="">（全て）</option><option value="FAQ">FAQ</option><option value="GENERATED_AI">生成AI</option></SelectField>
      <SelectField label="評価：" value={rating} onChange={(e) => setRating(e.target.value)}><option value="">（全て）</option><option value="RATED">Good＆Bad</option><option value="GOOD">Goodのみ</option><option value="BAD">Badのみ</option><option value="NONE">評価なし</option></SelectField>
      <SelectField label="コメント：" value={comment} onChange={(e) => setComment(e.target.value)}><option value="">（全て）</option><option value="WITH">コメント有</option><option value="WITHOUT">コメントなし</option></SelectField>
      <SelectField label="ユーザ種別：" value={role} onChange={(e) => setRole(e.target.value)}><option value="">（全て）</option><option value="staff">職員</option><option value="admin">システム管理者</option></SelectField>
      <FormField label="ユーザID：" value={userIds} placeholder="カンマ区切りで複数指定" onChange={(e) => setUserIds(e.target.value)} />
      <Button variant="download" icon={<AdminIcon name="download" size={18} />} disabled={loading} onClick={() => void download()}>{loading ? "作成中..." : "履歴ダウンロード"}</Button>
    </section>
  </AdminLayout>;
}
