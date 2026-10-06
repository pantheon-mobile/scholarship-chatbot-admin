import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Header } from "../components/admin/Header";

afterEach(cleanup);

it("ユーザーメニューはログアウトだけを表示し、一括消去を提供しない", () => {
  const logout = vi.fn();
  render(<Header userName="管理者" userId="admin-1" onLogout={logout} />);
  fireEvent.click(screen.getByRole("button", { name: "管理者 ▾" }));
  expect(screen.queryByText("ID：admin-1")).toBeNull();
  expect(screen.queryByText("一括消去")).toBeNull();
  expect(screen.getAllByRole("menuitem").map((item) => item.textContent)).toEqual(["ログアウト"]);
  fireEvent.click(screen.getByRole("menuitem", { name: "ログアウト" }));
  expect(logout).toHaveBeenCalledOnce();
});
