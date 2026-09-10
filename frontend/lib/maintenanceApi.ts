import { authenticatedFetch } from "@/lib/authenticatedFetch";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function fetchMaintenanceCapabilities(): Promise<{ bulk_purge_enabled: boolean }> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/maintenance/capabilities`, { cache: "no-store" });
  if (!response.ok) return { bulk_purge_enabled: false };
  return response.json();
}

export async function purgeAllData(): Promise<void> {
  const response = await authenticatedFetch(`${apiBase}/api/v1/maintenance/purge`, { method: "POST" });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "一括消去に失敗しました。");
  }
}
