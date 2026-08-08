export const MAX_WEBSITE_URL_LENGTH = 500;

export function validateWebsiteUrl(value: string) {
  const url = value.trim();
  if (!url) return "URLを入力してください。";
  if (url.length > MAX_WEBSITE_URL_LENGTH || /\s/.test(url)) return "正しいURLを入力してください。";
  try {
    const parsed = new URL(url);
    if (!(["http:", "https:"] as string[]).includes(parsed.protocol) || !parsed.hostname) {
      return "正しいURLを入力してください。";
    }
  } catch {
    return "正しいURLを入力してください。";
  }
  return null;
}
