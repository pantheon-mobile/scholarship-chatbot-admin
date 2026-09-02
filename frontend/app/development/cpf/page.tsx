"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { loginWithDevelopmentCpf } from "@/lib/authApi";
import styles from "./page.module.css";

type Role = "admin" | "staff";

export default function DevelopmentCpfPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("admin");
  const [displayName, setDisplayName] = useState("");
  const [subject, setSubject] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!displayName.trim() || !subject.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      await loginWithDevelopmentCpf({
        role,
        display_name: displayName.trim(),
        subject: subject.trim(),
      });
      router.replace("/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ログインに失敗しました。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className={styles.main}>
      <section className={styles.card}>
        <p className={styles.badge}>開発環境専用</p>
        <h1>CPF模擬ログイン</h1>
        <p className={styles.description}>CPFからの遷移を模擬して、管理画面の権限別表示を確認します。</p>
        <form onSubmit={submit} className={styles.form}>
          <fieldset className={styles.roles}>
            <legend>ロール</legend>
            <label><input type="radio" name="role" value="admin" checked={role === "admin"} onChange={() => setRole("admin")} />システム管理者</label>
            <label><input type="radio" name="role" value="staff" checked={role === "staff"} onChange={() => setRole("staff")} />職員</label>
          </fieldset>
          <label className={styles.field}>
            <span>氏名</span>
            <input value={displayName} maxLength={500} autoComplete="name" placeholder="例：東京 太郎" onChange={(event) => setDisplayName(event.target.value)} />
          </label>
          <label className={styles.field}>
            <span>利用者ID</span>
            <input value={subject} maxLength={500} autoComplete="username" placeholder="例：staff-001" onChange={(event) => setSubject(event.target.value)} />
          </label>
          {error && <p className={styles.error} role="alert">{error}</p>}
          <button type="submit" className={styles.submit} disabled={busy || !displayName.trim() || !subject.trim()}>
            {busy ? "ログイン中..." : "チャットボット管理画面へ遷移"}
          </button>
        </form>
        <p className={styles.notice}>この画面は開発環境でのみ利用できます。</p>
      </section>
    </main>
  );
}
