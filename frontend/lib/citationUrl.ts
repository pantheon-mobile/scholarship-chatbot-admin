export function safeCitationUrl(value?: string | null): string | null {
  if (!value || /[\s\\\x00-\x1f\x7f]/.test(value)) return null;
  if (/^\/api\/v1\/chat\/sources\/[1-9][0-9]*\/download$/.test(value)) return `${process.env.NEXT_PUBLIC_API_URL ?? ""}${value}`;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? value : null;
  } catch { return null; }
}
