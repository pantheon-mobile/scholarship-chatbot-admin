import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AdminIcon } from "../components/admin/AdminIcon";
import { AdminLayout } from "../components/admin/AdminLayout";
import styles from "../components/admin/admin.module.css";

afterEach(cleanup);

describe("AdminLayout", () => {
  it("既定ではコンテンツを中央配置する", () => {
    render(<AdminLayout activeMenu="dashboard" onNavigate={() => undefined}>本文</AdminLayout>);

    expect(screen.getByText("本文").classList.contains(styles.contentAlignCenter)).toBe(true);
  });

  it("幅variantを維持したまま左寄せを選択できる", () => {
    render(<AdminLayout activeMenu="data-sources" contentWidth="default" contentAlign="start" onNavigate={() => undefined}>本文</AdminLayout>);

    const content = screen.getByText("本文");
    expect(content.classList.contains(styles.contentDefault)).toBe(true);
    expect(content.classList.contains(styles.contentAlignStart)).toBe(true);
  });

  it.each(["default", "wide", "full"] as const)("%s幅variantを適用できる", (contentWidth) => {
    render(<AdminLayout activeMenu="dashboard" contentWidth={contentWidth} onNavigate={() => undefined}>{contentWidth}</AdminLayout>);

    const content = screen.getByText(contentWidth);
    const widthClass = styles[`content${contentWidth[0].toUpperCase()}${contentWidth.slice(1)}`];
    expect(content.classList.contains(widthClass)).toBe(true);
  });

  it("HeaderとSidebarのアイコンを共通仕様で描画する", () => {
    const { container } = render(<AdminLayout activeMenu="data-sources" onNavigate={() => undefined}>本文</AdminLayout>);
    const icons = Array.from(container.querySelectorAll("svg"));

    expect(icons).toHaveLength(8);
    for (const icon of icons) {
      expect(icon.getAttribute("viewBox")).toBe("0 0 24 24");
      expect(icon.getAttribute("stroke")).toBe("currentColor");
      expect(icon.getAttribute("stroke-width")).toBe("1.9");
      expect(icon.getAttribute("stroke-linecap")).toBe("round");
      expect(icon.getAttribute("stroke-linejoin")).toBe("round");
      expect(icon.getAttribute("aria-hidden")).toBe("true");
    }

    const activeMenu = screen.getByRole("button", { name: "データソース管理" });
    expect(activeMenu.classList.contains(styles.activeMenu)).toBe(true);
    expect(activeMenu.getAttribute("aria-current")).toBe("page");
  });

  it("ダッシュボードを円形メーターと丸い目盛り、右上向きの針で描画する", () => {
    const { container } = render(<AdminIcon name="dashboard" />);
    const paths = Array.from(container.querySelectorAll("path"));
    const circles = Array.from(container.querySelectorAll("circle"));

    expect(paths.map((path) => path.getAttribute("d"))).toEqual(["m11 16.5 4.8-7.1"]);
    expect(circles).toHaveLength(6);
    expect(container.querySelector('circle[cx="12"][cy="12"][r="9"]')).not.toBeNull();
    expect(container.querySelector('circle[cx="11"][cy="16.5"][r="1.25"]')).not.toBeNull();
  });
});
