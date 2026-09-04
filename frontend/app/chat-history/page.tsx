"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AdminLayout, Button, FormField, PageHeader, Table, TableCell, TableFrame, TableHeaderCell, TableRow } from "@/components/admin";
import { initialDashboardPeriod } from "@/lib/dashboardDates";
import { fetchChatHistory } from "@/lib/reportingApi";
import { ChatHistoryResponse } from "@/types/reporting";
import styles from "./page.module.css";

const localTime = (value: string | null) => value ? new Intl.DateTimeFormat("ja-JP", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value)) : "－";

export default function ChatHistoryPage() {
  const router = useRouter();
  const [initial] = useState(() => initialDashboardPeriod());
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ChatHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async (nextPage = page) => {
    setLoading(true); setError("");
    try { setData(await fetchChatHistory(from, to, nextPage)); setPage(nextPage); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "チャット履歴を取得できませんでした。"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(1); }, []);
  const search = (event: FormEvent) => { event.preventDefault(); void load(1); };
  const lastPage = Math.max(1, Math.ceil((data?.total_count ?? 0) / (data?.page_size ?? 20)));

  return <AdminLayout activeMenu="chat-history" contentWidth="wide" contentAlign="start" onNavigate={(href) => router.push(href)}>
    <PageHeader title="チャット履歴" />
    <form className={styles.filters} onSubmit={search}>
      <FormField label="From" type="date" value={from} onChange={(event) => setFrom(event.target.value)} required />
      <span>～</span>
      <FormField label="To" type="date" value={to} onChange={(event) => setTo(event.target.value)} required />
      <Button type="submit" variant="primary" disabled={loading}>検索</Button>
    </form>
    <p className={styles.note}>質問・回答本文は保存せず、処理結果と評価のみ表示します。職員には本人の履歴だけが表示されます。</p>
    {error && <p className={styles.error} role="alert">{error}</p>}
    {loading ? <p>読み込み中...</p> : <>
      <p>チャット数　{data?.total_count ?? 0}件</p>
      <TableFrame><Table>
        <thead><TableRow><TableHeaderCell>開始日時</TableHeaderCell><TableHeaderCell>利用者氏名</TableHeaderCell><TableHeaderCell>利用者ID</TableHeaderCell><TableHeaderCell>ロール</TableHeaderCell><TableHeaderCell>サイト</TableHeaderCell><TableHeaderCell>応答</TableHeaderCell><TableHeaderCell>完了</TableHeaderCell><TableHeaderCell>失敗</TableHeaderCell><TableHeaderCell>FAQ</TableHeaderCell><TableHeaderCell>生成AI</TableHeaderCell><TableHeaderCell>回答NG</TableHeaderCell><TableHeaderCell>Good</TableHeaderCell><TableHeaderCell>Bad</TableHeaderCell></TableRow></thead>
        <tbody>{data?.items.map((item) => <TableRow key={item.session_id}><TableCell>{localTime(item.started_at)}</TableCell><TableCell>{item.user_name || item.user_label}</TableCell><TableCell>{item.user_id || "－"}</TableCell><TableCell>{item.user_role || "－"}</TableCell><TableCell>{item.user_site || "－"}</TableCell><TableCell>{item.response_count}</TableCell><TableCell>{item.completed_count}</TableCell><TableCell>{item.failed_count}</TableCell><TableCell>{item.faq_count}</TableCell><TableCell>{item.generated_ai_count}</TableCell><TableCell>{item.no_answer_count}</TableCell><TableCell>{item.good_count}</TableCell><TableCell>{item.bad_count}</TableCell></TableRow>)}</tbody>
      </Table></TableFrame>
      {!data?.items.length && <p className={styles.empty}>対象期間の履歴はありません。</p>}
      <div className={styles.paging}><Button variant="secondary" disabled={page <= 1} onClick={() => void load(page - 1)}>前へ</Button><span>{page} / {lastPage}</span><Button variant="secondary" disabled={page >= lastPage} onClick={() => void load(page + 1)}>次へ</Button></div>
    </>}
  </AdminLayout>;
}
