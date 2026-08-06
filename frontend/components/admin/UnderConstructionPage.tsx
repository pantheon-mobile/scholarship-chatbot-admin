"use client";

import { useRouter } from "next/navigation";
import { AdminLayout } from "./AdminLayout";
import { Button } from "./Button";

export function UnderConstructionPage({ title }: { title: string }) {
  const router = useRouter();
  return (
    <AdminLayout activeMenu="data-sources" contentWidth="default" contentAlign="start" onNavigate={(href) => router.push(href)}>
      <h1>{title}</h1>
      <p>この画面は未実装です。</p>
      <Button variant="secondary" onClick={() => router.push("/data-sources")}>データソース一覧に戻る</Button>
    </AdminLayout>
  );
}
