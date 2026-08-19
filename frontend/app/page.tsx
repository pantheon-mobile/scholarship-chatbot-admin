"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AdminLayout, Button, FormField, PageHeader, Table, TableCell, TableFrame, TableHeaderCell, TableRow } from "@/components/admin";
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

function MetricRow({ left, leftValue, right, rightValue }: {
  left: string; leftValue: string; right?: string; rightValue?: string;
}) {
  return <TableRow>
    <TableHeaderCell scope="row" className={styles.metricLabel}>{left}</TableHeaderCell>
    <TableCell className={styles.metricValue}>{leftValue}</TableCell>
    <TableHeaderCell scope="row" className={styles.metricLabel}>{right ?? ""}</TableHeaderCell>
    <TableCell className={styles.metricValue}>{rightValue ?? ""}</TableCell>
  </TableRow>;
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

  return <AdminLayout activeMenu="dashboard" contentWidth="wide" onNavigate={(href) => router.push(href)}>
    <PageHeader title="ダッシュボード" />
    <form className={styles.periodForm} onSubmit={aggregate} aria-label="集計期間">
      <FormField id="dashboard-from" label="From" type="date" required value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
      <span className={styles.periodSeparator} aria-hidden="true">～</span>
      <FormField id="dashboard-to" label="To" type="date" required value={toDate} onChange={(event) => setToDate(event.target.value)} />
      <Button variant="primary" type="submit" disabled={loading}>集計</Button>
    </form>

    {error && <div className={styles.error} role="alert">{error}</div>}
    {loading && <p className={styles.loading} role="status">集計中です。</p>}

    {!loading && dashboard && <div className={styles.dashboardContent}>
      <section aria-labelledby="basic-metrics-title">
        <h2 id="basic-metrics-title" className={styles.sectionTitle}>基本指標</h2>
        <TableFrame>
          <Table className={styles.metricsTable}>
            <tbody>
              <MetricRow left="アクセス数" leftValue={count(dashboard.basic_metrics.access_count)} right="アクセスユーザ数" rightValue={count(dashboard.basic_metrics.access_user_count)} />
              <MetricRow left="チャット数" leftValue={count(dashboard.basic_metrics.chat_count)} right="チャットユーザ数" rightValue={count(dashboard.basic_metrics.chat_user_count)} />
              <MetricRow left="1日平均チャット数" leftValue={decimal(dashboard.basic_metrics.average_chats_per_day)} right="1人あたりチャット数" rightValue={decimal(dashboard.basic_metrics.average_chats_per_user)} />
              <MetricRow left="応答数" leftValue={count(dashboard.basic_metrics.response_count)} right="1チャットあたり平均応答数" rightValue={decimal(dashboard.basic_metrics.average_responses_per_chat)} />
              <MetricRow left="1人あたり平均応答数" leftValue={decimal(dashboard.basic_metrics.average_responses_per_user)} right="応答時間（平均／秒）" rightValue={decimal(dashboard.basic_metrics.response_time.average_seconds)} />
              <MetricRow left="応答時間（最短～最長／秒）" leftValue={dashboard.basic_metrics.response_time.minimum_seconds === null ? "－" : `${decimal(dashboard.basic_metrics.response_time.minimum_seconds)} ～ ${decimal(dashboard.basic_metrics.response_time.maximum_seconds)}`} right="有効回答数" rightValue={count(dashboard.basic_metrics.valid_answer_count)} />
              <MetricRow left="回答NG数" leftValue={count(dashboard.basic_metrics.no_answer_count)} right="回答率" rightValue={decimal(dashboard.basic_metrics.answer_rate, "%")} />
              <MetricRow left="Good数" leftValue={count(dashboard.basic_metrics.good_count)} right="Bad数" rightValue={count(dashboard.basic_metrics.bad_count)} />
              <MetricRow left="評価なし" leftValue={count(dashboard.basic_metrics.unrated_count)} right="満足度" rightValue={decimal(dashboard.basic_metrics.satisfaction_rate, "%")} />
              <MetricRow left="コメント総数" leftValue={count(dashboard.basic_metrics.comment_count)} right="コメント数（Good）" rightValue={count(dashboard.basic_metrics.good_comment_count)} />
              <MetricRow left="コメント数（Bad）" leftValue={count(dashboard.basic_metrics.bad_comment_count)} />
            </tbody>
          </Table>
        </TableFrame>
      </section>

      <section aria-labelledby="answer-types-title">
        <h2 id="answer-types-title" className={styles.sectionTitle}>チャット回答種別利用状況</h2>
        <TableFrame>
          <Table className={styles.metricsTable}>
            <tbody>
              <MetricRow left="総回答数" leftValue={count(dashboard.answer_types.total_count)} right="FAQ回答数" rightValue={count(dashboard.answer_types.faq_count)} />
              <MetricRow left="FAQ回答率" leftValue={decimal(dashboard.answer_types.faq_rate, "%")} right="生成AI回答数" rightValue={count(dashboard.answer_types.generated_ai_count)} />
              <MetricRow left="生成AI回答率" leftValue={decimal(dashboard.answer_types.generated_ai_rate, "%")} right="回答NG数" rightValue={count(dashboard.answer_types.no_answer_count)} />
            </tbody>
          </Table>
        </TableFrame>
      </section>

      <div className={styles.breakdownGrid}>
        <section aria-labelledby="time-title">
          <h2 id="time-title" className={styles.sectionTitle}>時間帯別利用状況</h2>
          <TableFrame><Table>
            <thead><TableRow><TableHeaderCell>時間帯</TableHeaderCell><TableHeaderCell>チャット数</TableHeaderCell><TableHeaderCell>応答数</TableHeaderCell></TableRow></thead>
            <tbody>{dashboard.time_buckets.map((item) => <TableRow key={item.key}><TableCell>{item.label}</TableCell><TableCell>{count(item.chat_count)}</TableCell><TableCell>{count(item.response_count)}</TableCell></TableRow>)}</tbody>
          </Table></TableFrame>
        </section>
        <section aria-labelledby="weekday-title">
          <h2 id="weekday-title" className={styles.sectionTitle}>曜日別利用状況</h2>
          <TableFrame><Table>
            <thead><TableRow><TableHeaderCell>曜日</TableHeaderCell><TableHeaderCell>チャット数</TableHeaderCell><TableHeaderCell>応答数</TableHeaderCell></TableRow></thead>
            <tbody>{dashboard.weekday_buckets.map((item) => <TableRow key={item.key}><TableCell>{item.label}</TableCell><TableCell>{count(item.chat_count)}</TableCell><TableCell>{count(item.response_count)}</TableCell></TableRow>)}</tbody>
          </Table></TableFrame>
        </section>
      </div>
    </div>}
  </AdminLayout>;
}
