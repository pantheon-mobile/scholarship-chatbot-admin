import { Fragment, ReactNode } from "react";

type LinkedPlainTextProps = { text: string };

const urlPattern = /https?:\/\/[^\s<>"']+/g;
const trailingPunctuation = /[.,、。!！?？:：;；)）\]】}」』]+$/;

export function LinkedPlainText({ text }: LinkedPlainTextProps) {
  const parts: ReactNode[] = [];
  let cursor = 0;

  for (const match of text.matchAll(urlPattern)) {
    const index = match.index ?? 0;
    if (index > cursor) parts.push(text.slice(cursor, index));
    const candidate = match[0];
    const trailing = candidate.match(trailingPunctuation)?.[0] ?? "";
    const href = trailing ? candidate.slice(0, -trailing.length) : candidate;
    let linkable = false;
    try {
      const parsed = new URL(href);
      linkable = parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch {}
    parts.push(linkable
      ? <a href={href} target="_blank" rel="noopener noreferrer" key={`${index}-${href}`}>{href}</a>
      : href);
    if (trailing) parts.push(trailing);
    cursor = index + candidate.length;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));

  return <>{parts.map((part, index) => <Fragment key={index}>{part}</Fragment>)}</>;
}
