export type DashboardBasicMetrics = Record<string, { name: string; visible: 0 | 1 }>;
const metricIds = new Set(["access_count", "access_user_count", "chat_count", "chat_user_count", "average_chats_per_day", "average_chats_per_user", "response_count", "average_responses_per_chat", "average_responses_per_user", "response_time_average", "response_time_range", "valid_answer_count", "no_answer_count", "answer_rate", "good_count", "bad_count", "unrated_count", "satisfaction_rate", "comment_count", "good_comment_count", "bad_comment_count"]);

export function dashboardMetricsEnvironment(settings: DashboardBasicMetrics | undefined): string {
  if (settings === undefined) return "";
  if (settings === null || typeof settings !== "object" || Array.isArray(settings)) {
    throw new Error("dashboardBasicMetrics must be an object");
  }
  for (const [key, entry] of Object.entries(settings)) {
    if (!metricIds.has(key)) throw new Error(`Unknown dashboard metric: ${key}`);
    if (!entry || typeof entry !== "object" || Array.isArray(entry)
      || Object.keys(entry).sort().join(",") !== "name,visible"
      || typeof entry.name !== "string" || !entry.name.trim()
      || (entry.visible !== 0 && entry.visible !== 1)) {
      throw new Error(`${key}: name must be a nonempty string and visible must be 0 or 1`);
    }
  }
  return JSON.stringify(settings);
}
