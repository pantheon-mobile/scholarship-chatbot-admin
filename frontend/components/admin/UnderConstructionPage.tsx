"use client";

import { useRouter } from "next/navigation";
import { AdminLayout } from "./AdminLayout";
import { Button } from "./Button";
import { AdminMenuKey } from "./Sidebar";

type UnderConstructionPageProps = {
  title: string;
  activeMenu?: AdminMenuKey;
  backHref?: string;
  backLabel?: string;
};

export function UnderConstructionPage({
  title,
  activeMenu = "data-sources",
  backHref = "/data-sources",
  backLabel = "一覧に戻る",
}: UnderConstructionPageProps) {
  const router = useRouter();
  return (
    <AdminLayout activeMenu={activeMenu} contentWidth="default" contentAlign="start" onNavigate={(href) => router.push(href)}>
      <h1>{title}</h1>
      <p>この画面は未実装です。</p>
      <Button variant="secondary" onClick={() => router.push(backHref)}>{backLabel}</Button>
    </AdminLayout>
  );
}
