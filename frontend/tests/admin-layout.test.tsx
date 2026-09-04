import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminIcon } from "../components/admin/AdminIcon";
import { AdminLayout } from "../components/admin/AdminLayout";
import styles from "../components/admin/admin.module.css";
import { Sidebar } from "../components/admin/Sidebar";

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

  it("新ヘッダ・サイドバーを全画面の既定仕様として適用する", () => {
    const { container } = render(<AdminLayout activeMenu="data-sources" onNavigate={() => undefined}>本文</AdminLayout>);

    expect(screen.getByRole("button", { name: "サイドメニューを閉じる" })).not.toBeNull();
    expect(screen.getByRole("button", { name: "チャットサイト" })).not.toBeNull();
    const userMenuButton = screen.getByRole("button", { name: "東京太郎 ▾" });
    expect(userMenuButton).not.toBeNull();
    expect(screen.queryByRole("button", { name: "ログアウト" })).toBeNull();
    fireEvent.click(userMenuButton);
    expect(screen.getByText("ID：-")).not.toBeNull();
    expect(screen.getByRole("menuitem", { name: "閉じる" })).not.toBeNull();
    expect(screen.getByRole("menuitem", { name: "ログアウト" })).not.toBeNull();
    expect(container.querySelector(`.${styles.menuIcon}`)).toBeNull();
  });

  it("黒いヘッダー上でログイン利用者名を白色表示する", () => {
    render(<AdminLayout activeMenu="dashboard" userName="笠井 美治" onNavigate={() => undefined}>本文</AdminLayout>);

    expect(screen.getByRole("button", { name: "笠井 美治 ▾" }).classList.contains(styles.userMenuButton)).toBe(true);
  });

  it("チャットサイトから認証済みチャット画面へ遷移する", () => {
    const onNavigate = vi.fn();
    render(<AdminLayout activeMenu="dashboard" onNavigate={onNavigate}>本文</AdminLayout>);

    fireEvent.click(screen.getByRole("button", { name: "チャットサイト" }));

    expect(onNavigate).toHaveBeenCalledWith("/chat");
  });

  it("ログアウト後に開発用CPF画面へ遷移する", async () => {
    const onNavigate = vi.fn();
    render(<AdminLayout activeMenu="dashboard" onNavigate={onNavigate}>本文</AdminLayout>);

    fireEvent.click(screen.getByRole("button", { name: "東京太郎 ▾" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "ログアウト" }));

    await vi.waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/development/cpf"));
  });

  it("職員にはシステム管理者専用メニューを表示しない", () => {
    render(<Sidebar activeMenu="dashboard" role="staff" onNavigate={() => undefined} />);

    expect(screen.getByRole("button", { name: "ダッシュボード" })).not.toBeNull();
    expect(screen.getByRole("button", { name: "ＦＡＱ管理" })).not.toBeNull();
    expect(screen.getByRole("button", { name: "チャット履歴" })).not.toBeNull();
    expect(screen.queryByRole("button", { name: "データソース管理" })).toBeNull();
    expect(screen.queryByRole("button", { name: "カテゴリ設定" })).toBeNull();
    expect(screen.queryByRole("button", { name: "利用状況管理" })).toBeNull();
  });

  it("ハンバーガーでアイコン表示へ切り替え、折りたたみ中もメニュー遷移できる", () => {
    const onNavigate = vi.fn();
    const { container } = render(<AdminLayout activeMenu="data-sources" onNavigate={onNavigate}>本文</AdminLayout>);

    fireEvent.click(screen.getByRole("button", { name: "サイドメニューを閉じる" }));
    expect(container.firstElementChild?.classList.contains(styles.sidebarCollapsed)).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "ダッシュボード" }));
    expect(onNavigate).toHaveBeenCalledWith("/");
    fireEvent.click(screen.getByRole("button", { name: "サイドメニューを開く" }));
    expect(container.firstElementChild?.classList.contains(styles.sidebarCollapsed)).toBe(false);
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
