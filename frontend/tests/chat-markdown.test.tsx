import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MarkdownAnswer } from "../app/chat/MarkdownAnswer";


afterEach(cleanup);

describe("chat Markdown answer", () => {
  it("日本語の括弧直後の太字を表示し、コードとエスケープは維持する", () => {
    const { container } = render(<MarkdownAnswer content={'**2026年4月14日（火）～4月22日（水）**です。\n\n`**（水）**です。`\n\n\\*\\*（水）\\*\\*です。'} />);
    expect(container.querySelectorAll("strong")).toHaveLength(1);
    expect(container.querySelector("strong")?.textContent).toBe("2026年4月14日（火）～4月22日（水）");
    expect(container.querySelector("code")?.textContent).toBe("**（水）**です。");
  });
  it("太字、箇条書き、リンクを描画する", () => {
    const { container } = render(
      <MarkdownAnswer content={"**本採用**になります。\n\n- 進学届を提出\n- 期限を確認\n\nhttps://example.com/guide"} />,
    );

    expect(container.querySelector("strong")?.textContent).toBe("本採用");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    const link = screen.getByRole("link", { name: "https://example.com/guide" });
    expect(link.getAttribute("href")).toBe("https://example.com/guide");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("回答中のHTMLを実行可能な要素として描画しない", () => {
    const { container } = render(
      <MarkdownAnswer content={'<script>alert("危険")</script><img src=x onerror=alert(1)>'} />,
    );

    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });
});
