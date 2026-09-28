"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AdminLayout, Button, FormField, PageHeader } from "@/components/admin";
import { fetchDashboard } from "@/lib/dashboardApi";
import { initialDashboardPeriod } from "@/lib/dashboardDates";
import { DashboardResponse } from "@/types/dashboard";
import styles from "./page.module.css";

function decimal(value: number | null, suffix = "") {
  return value === null ? "－" : `${value.toFixed(1)}${suffix}`;
}

function count(value: number) {
  return value.toLocaleString("ja-JP");
}

function Metric({ label, value }: { label: ReactNode; value: string }) {
  return <div className={styles.metric}>
    <dt>{label}</dt>
    <dd>{value}</dd>
  </div>;
}

function BreakdownRow({ label, chatCount, responseCount }: {
  label: string;
  chatCount: number;
  responseCount: number;
}) {
  return <div className={styles.breakdownRow}>
    <span>{label}</span>
    <span>{count(chatCount)}</span>
    <span>{count(responseCount)}</span>
  </div>;
}

export default function DashboardPage() {
  const router = useRouter();
  const [initial] = useState(() => initialDashboardPeriod());
  const [fromDate, setFromDate] = useState(initial.from);
  const [toDate, setToDate] = useState(initial.to);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (from: string, to: string) => {
    setLoading(true);
    setError("");
    try {
      setDashboard(await fetchDashboard(from, to));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ダッシュボードの集計に失敗しました。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(initial.from, initial.to); }, [initial, load]);

  const aggregate = (event: FormEvent) => {
    event.preventDefault();
    void load(fromDate, toDate);
  };

  const metrics = dashboard ? [
    { id: "access_count", label: "アクセス数", value: count(dashboard.basic_metrics.access_count) },
    { id: "access_user_count", label: "アクセスユーザ数", value: count(dashboard.basic_metrics.access_user_count) },
    { id: "chat_count", label: "チャット数", value: count(dashboard.basic_metrics.chat_count) },
    { id: "chat_user_count", label: "チャットユーザ数", value: count(dashboard.basic_metrics.chat_user_count) },
    { id: "average_chats_per_day", label: "1日平均チャット数", value: decimal(dashboard.basic_metrics.average_chats_per_day) },
    { id: "average_chats_per_user", label: "1人あたりチャット数", value: decimal(dashboard.basic_metrics.average_chats_per_user) },
    { id: "response_count", label: "応答数", value: count(dashboard.basic_metrics.response_count) },
    { id: "average_responses_per_chat", label: "1チャットあたり平均応答数", value: decimal(dashboard.basic_metrics.average_responses_per_chat) },
    { id: "average_responses_per_user", label: "1人あたり平均応答数", value: decimal(dashboard.basic_metrics.average_responses_per_user) },
    { id: "response_time_average", label: <>応答時間<br />（平均／秒）</>, value: decimal(dashboard.basic_metrics.response_time.average_seconds) },
    { id: "response_time_range", label: <>応答時間<br />（最短 - 最長／秒）</>, value: dashboard.basic_metrics.response_time.minimum_seconds === null ? "－" : `${decimal(dashboard.basic_metrics.response_time.minimum_seconds)} - ${decimal(dashboard.basic_metrics.response_time.maximum_seconds)}` },
    { id: "valid_answer_count", label: "有効回答数", value: count(dashboard.basic_metrics.valid_answer_count) },
    { id: "no_answer_count", label: "回答NG数", value: count(dashboard.basic_metrics.no_answer_count) },
    { id: "answer_rate", label: "回答率", value: decimal(dashboard.basic_metrics.answer_rate, "%") },
    { id: "good_count", label: "Good数", value: count(dashboard.basic_metrics.good_count) },
    { id: "bad_count", label: "Bad数", value: count(dashboard.basic_metrics.bad_count) },
    { id: "unrated_count", label: "評価なし", value: count(dashboard.basic_metrics.unrated_count) },
    { id: "satisfaction_rate", label: "満足度", value: decimal(dashboard.basic_metrics.satisfaction_rate, "%") },
    { id: "comment_count", label: "コメント総数", value: count(dashboard.basic_metrics.comment_count) },
    { id: "good_comment_count", label: <>コメント数<br />（Good）</>, value: count(dashboard.basic_metrics.good_comment_count) },
    { id: "bad_comment_count", label: <>コメント数<br />（Bad）</>, value: count(dashboard.basic_metrics.bad_comment_count) },
  ].filter((metric) => dashboard.visible_basic_metrics === undefined || dashboard.visible_basic_metrics.includes(metric.id)) : [];

  return <AdminLayout activeMenu="dashboard" contentWidth="wide" onNavigate={(href) => router.push(href)}>
    <PageHeader title="ダッシュボード" />
    <form className={styles.periodForm} onSubmit={aggregate} aria-label="集計期間">
      <span className={styles.periodLabel}>期間指定：</span>
      <FormField id="dashboard-from" aria-label="開始日" type="date" required value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
      <span className={styles.periodSeparator} aria-hidden="true">～</span>
      <FormField id="dashboard-to" aria-label="終了日" type="date" required value={toDate} onChange={(event) => setToDate(event.target.value)} />
      <Button variant="primary" type="submit" disabled={loading}>集計</Button>
    </form>

    {error && <div className={styles.error} role="alert">{error}</div>}
    {loading && <p className={styles.loading} role="status">集計中です。</p>}

    {!loading && dashboard && <div className={styles.dashboardContent}>
      {metrics.length > 0 && <dl className={styles.metricsPanel} aria-label="基本指標">
        {metrics.map((metric) => <Metric key={metric.id} label={metric.label} value={metric.value} />)}
      </dl>}

      <div className={styles.breakdownGrid}>
        <section className={styles.breakdownPanel} aria-labelledby="answer-types-title">
          <h2 id="answer-types-title">チャット種別利用</h2>
          <div className={styles.simpleList}>
            <div><span>総回答数</span><strong>{count(dashboard.answer_types.total_count)}</strong></div>
            <div><span>FAQ 回答数</span><strong>{count(dashboard.answer_types.faq_count)}</strong></div>
            <div><span>FAQ 回答率</span><strong>{decimal(dashboard.answer_types.faq_rate, "%")}</strong></div>
            <div><span>生成 AI 回答数</span><strong>{count(dashboard.answer_types.generated_ai_count)}</strong></div>
            <div><span>生成 AI 回答率</span><strong>{decimal(dashboard.answer_types.generated_ai_rate, "%")}</strong></div>
            <div><span>回答 NG 数</span><strong>{count(dashboard.answer_types.no_answer_count)}</strong></div>
          </div>
        </section>
        <section className={styles.breakdownPanel} aria-labelledby="time-title">
          <h2 id="time-title">時間帯別利用</h2>
          <div className={styles.breakdownHeader}><span /><span>チャット数</span><span>応答数</span></div>
          {dashboard.time_buckets.map((item) => <BreakdownRow key={item.key} label={item.label} chatCount={item.chat_count} responseCount={item.response_count} />)}
        </section>
        <section className={styles.breakdownPanel} aria-labelledby="weekday-title">
          <h2 id="weekday-title">曜日別利用</h2>
          <div className={styles.breakdownHeader}><span /><span>チャット数</span><span>応答数</span></div>
          {dashboard.weekday_buckets.map((item) => <BreakdownRow key={item.key} label={item.label} chatCount={item.chat_count} responseCount={item.response_count} />)}
        </section>
      </div>
    </div>}
  </AdminLayout>;
}
