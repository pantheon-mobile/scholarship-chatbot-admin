"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { AdminLayout, Button, FormField, PageHeader } from "@/components/admin";
import { initialDashboardPeriod } from "@/lib/dashboardDates";
import { downloadUsageCsv } from "@/lib/reportingApi";
import styles from "./page.module.css";

export default function UsagePage() {
  const router = useRouter();
  const [initial] = useState(() => initialDashboardPeriod());
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const download = async (kind: "users" | "access-logs" | "operation-logs") => {
    setBusy(kind); setError("");
    try { await downloadUsageCsv(kind, from, to); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "CSVを取得できませんでした。"); }
    finally { setBusy(""); }
  };
  return <AdminLayout activeMenu="usage" contentWidth="default" contentAlign="start" onNavigate={(href) => router.push(href)}>
    <PageHeader title="利用状況管理" />
    <form className={styles.filters} onSubmit={(event: FormEvent) => event.preventDefault()}>
      <FormField label="From" type="date" value={from} onChange={(event) => setFrom(event.target.value)} required />
      <span>～</span>
      <FormField label="To" type="date" value={to} onChange={(event) => setTo(event.target.value)} required />
    </form>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <section className={styles.downloads}>
      <h2>ダウンロード</h2>
      <Button variant="download" disabled={Boolean(busy)} onClick={() => void download("users")}>{busy === "users" ? "作成中..." : "ユーザリストをダウンロード"}</Button>
      <Button variant="download" disabled={Boolean(busy)} onClick={() => void download("access-logs")}>{busy === "access-logs" ? "作成中..." : "アクセスログをダウンロード"}</Button>
      <Button variant="download" disabled={Boolean(busy)} onClick={() => void download("operation-logs")}>{busy === "operation-logs" ? "作成中..." : "操作ログをダウンロード"}</Button>
    </section>
  </AdminLayout>;
}
