"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CpfExchangeError, exchangeCpfToken } from "@/lib/authApi";
import styles from "./page.module.css";

export default function CpfSsoPage() {
  const router = useRouter();
  const started = useRef(false);
  const [error, setError] = useState("");
  const [returnUrl, setReturnUrl] = useState<string | null>(null);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const params = new URLSearchParams(window.location.hash.slice(1));
    const token = params.get("token");
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);

    if (!token) {
      setError("認証情報を確認できませんでした。CPFからもう一度アクセスしてください。");
      return;
    }

    exchangeCpfToken(token)
      .then(() => router.replace("/"))
      .catch((reason: unknown) => {
        setError(
          reason instanceof Error
            ? reason.message
            : "認証に失敗しました。CPFからもう一度アクセスしてください。",
        );
        if (reason instanceof CpfExchangeError) setReturnUrl(reason.returnUrl);
      });
  }, [router]);

  return (
    <main className={styles.main}>
      <section className={styles.card} aria-live="polite">
        <h1>奨学金チャットボット</h1>
        {error ? (
          <>
            <p className={styles.error}>{error}</p>
            <p className={styles.help}>この画面を再読み込みせず、CPFのメニューから入り直してください。</p>
            {returnUrl && <Link href={returnUrl} className={styles.link}>CPFへ戻る</Link>}
          </>
        ) : (
          <>
            <div className={styles.spinner} aria-hidden="true" />
            <p>ログイン情報を確認しています。</p>
          </>
        )}
      </section>
    </main>
  );
}
