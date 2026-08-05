import { createRef } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Button } from "../components/admin/Button";
import styles from "../components/admin/admin.module.css";

afterEach(cleanup);

describe("Button", () => {
  it("refをbutton要素へ渡し、意図しないsubmitを発生させない", () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>キャンセル</Button>);

    const button = screen.getByRole("button", { name: "キャンセル" });
    expect(ref.current).toBe(button);
    expect(button.getAttribute("type")).toBe("button");
  });

  it.each([
    ["primary", "primary"],
    ["secondary", "neutral"],
    ["danger", "danger"],
    ["text", "primary"],
    ["download", "primary"],
    ["add", "primary"],
  ] as const)("%s variantに%sのfocus toneを適用する", (variant, focusTone) => {
    render(<Button variant={variant}>{variant}</Button>);

    const button = screen.getByRole("button", { name: variant });
    const focusClass = styles[`focus${focusTone[0].toUpperCase()}${focusTone.slice(1)}`];
    expect(button.classList.contains(focusClass)).toBe(true);
  });

  it("text variantでもdanger用途を明示できる", () => {
    render(<Button variant="text" focusTone="danger">削除</Button>);

    const button = screen.getByRole("button", { name: "削除" });
    expect(button.classList.contains(styles.focusDanger)).toBe(true);
    expect(button.classList.contains(styles.focusPrimary)).toBe(false);
  });
});
