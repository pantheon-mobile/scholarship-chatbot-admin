import type { Metadata } from "next";

export function siteMetadata(env: Record<string, string | undefined> = process.env): Metadata {
  const favicon = env.SITE_FAVICON_URL?.trim();
  // Only same-site paths or HTTPS images are accepted as browser icon URLs.
  const safeIcon = favicon && (/^\/(?!\/)/.test(favicon) || /^https:\/\//i.test(favicon));
  return {
    title: env.SITE_BROWSER_TITLE?.trim() || "Scholarship Chatbot",
    description: "Scholarship chatbot",
    ...(safeIcon ? { icons: { icon: favicon } } : {}),
  };
}
