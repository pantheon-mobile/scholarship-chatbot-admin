"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AdminIcon, AdminLayout, Button, FormField, PageHeader, SelectField } from "@/components/admin";
import { initialDashboardPeriod } from "@/lib/dashboardDates";
import { downloadUsageCsv } from "@/lib/reportingApi";
import styles from "./page.module.css";

export default function UsagePage() {
  const router = useRouter();
  const [initial] = useState(() => initialDashboardPeriod());
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [userRole, setUserRole] = useState("");
  const [accessSurface, setAccessSurface] = useState("");
  const [accessRole, setAccessRole] = useState("");
  const [accessUserIds, setAccessUserIds] = useState("");
  const [operationSurface, setOperationSurface] = useState("");
  const [operationType, setOperationType] = useState("");
  const [operationRole, setOperationRole] = useState("");
  const [operationUserIds, setOperationUserIds] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const download = async (kind: "users" | "access-logs" | "operation-logs") => {
    setBusy(kind); setError("");
    const filters = kind === "users"
      ? { role: userRole }
      : kind === "access-logs"
        ? { surface: accessSurface, role: accessRole, userIds: accessUserIds }
        : { surface: operationSurface, operationType, role: operationRole, userIds: operationUserIds };
    try { await downloadUsageCsv(kind, from, to, filters); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "CSVを取得できませんでした。"); }
    finally { setBusy(""); }
  };
  return <AdminLayout activeMenu="usage" contentWidth="default" contentAlign="start" onNavigate={(href) => router.push(href)}>
    <PageHeader title="ユーザ利用状況ダウンロード" />
    {error && <p className={styles.error} role="alert">{error}</p>}
    <section className={styles.section}>
      <h2>【ユーザリスト】</h2>
      <div className={styles.userFilters}><SelectField label="ユーザ種別：" value={userRole} onChange={(event) => setUserRole(event.target.value)}><option value="">（全て）</option><option value="staff">職員（一般）</option><option value="admin">職員（管理者）</option></SelectField></div>
      <Button variant="download" icon={<AdminIcon name="download" size={18} />} disabled={Boolean(busy)} onClick={() => void download("users")}>{busy === "users" ? "作成中..." : "ユーザリストダウンロード"}</Button>
    </section>
    <section className={styles.section}>
      <h2>【アクセスログ】</h2>
      <div className={styles.grid}>
        <div className={styles.period}><span>期間指定：</span><FormField aria-label="アクセスログFrom" type="date" value={from} onChange={(event) => setFrom(event.target.value)} required /><span>～</span><FormField aria-label="アクセスログTo" type="date" value={to} onChange={(event) => setTo(event.target.value)} required /></div>
        <SelectField label="サイト：" value={accessSurface} onChange={(event) => setAccessSurface(event.target.value)}><option value="">（全て）</option><option value="CHAT">チャット</option><option value="ADMIN">管理サイト</option></SelectField>
        <SelectField label="ユーザ種別：" value={accessRole} onChange={(event) => setAccessRole(event.target.value)}><option value="">（全て）</option><option value="staff">職員（一般）</option><option value="admin">職員（管理者）</option></SelectField>
        <FormField label="ユーザID：" value={accessUserIds} placeholder="カンマ区切りで複数指定" onChange={(event) => setAccessUserIds(event.target.value)} />
      </div>
      <Button variant="download" icon={<AdminIcon name="download" size={18} />} disabled={Boolean(busy)} onClick={() => void download("access-logs")}>{busy === "access-logs" ? "作成中..." : "アクセスログダウンロード"}</Button>
    </section>
    <section className={styles.section}>
      <h2>【操作ログ】</h2>
      <div className={styles.grid}>
        <div className={styles.period}><span>期間指定：</span><FormField aria-label="操作ログFrom" type="date" value={from} onChange={(event) => setFrom(event.target.value)} required /><span>～</span><FormField aria-label="操作ログTo" type="date" value={to} onChange={(event) => setTo(event.target.value)} required /></div>
        <SelectField label="サイト：" value={operationSurface} onChange={(event) => setOperationSurface(event.target.value)}><option value="">（全て）</option><option value="CHAT">チャット</option><option value="ADMIN">管理サイト</option></SelectField>
        <SelectField label="操作種別：" value={operationType} onChange={(event) => setOperationType(event.target.value)}><option value="">（全て）</option><option value="CREATE">登録</option><option value="UPDATE">更新</option><option value="DELETE">削除</option><option value="DOWNLOAD">ダウンロード</option><option value="UPLOAD">アップロード</option></SelectField>
        <SelectField label="ユーザ種別：" value={operationRole} onChange={(event) => setOperationRole(event.target.value)}><option value="">（全て）</option><option value="staff">職員（一般）</option><option value="admin">職員（管理者）</option></SelectField>
        <FormField label="ユーザID：" value={operationUserIds} placeholder="カンマ区切りで複数指定" onChange={(event) => setOperationUserIds(event.target.value)} />
      </div>
      <Button variant="download" icon={<AdminIcon name="download" size={18} />} disabled={Boolean(busy)} onClick={() => void download("operation-logs")}>{busy === "operation-logs" ? "作成中..." : "操作ログダウンロード"}</Button>
    </section>
  </AdminLayout>;
}
