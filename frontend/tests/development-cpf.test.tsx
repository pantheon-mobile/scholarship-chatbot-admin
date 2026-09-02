import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { replace, loginWithDevelopmentCpf } = vi.hoisted(() => ({
  replace: vi.fn(),
  loginWithDevelopmentCpf: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("../lib/authApi", () => ({ loginWithDevelopmentCpf }));

import DevelopmentCpfPage from "../app/development/cpf/page";

beforeEach(() => {
  replace.mockReset();
  loginWithDevelopmentCpf.mockReset();
  loginWithDevelopmentCpf.mockResolvedValue({
    subject: "staff-001", display_name: "開発 職員", role: "staff", site: "faculty",
  });
});

afterEach(cleanup);

describe("CPF模擬ログイン", () => {
  it("ロール、氏名、利用者IDを指定してダッシュボードへ遷移する", async () => {
    render(<DevelopmentCpfPage />);

    fireEvent.click(screen.getByRole("radio", { name: "職員" }));
    fireEvent.change(screen.getByLabelText("氏名"), { target: { value: " 開発 職員 " } });
    fireEvent.change(screen.getByLabelText("利用者ID"), { target: { value: " staff-001 " } });
    fireEvent.click(screen.getByRole("button", { name: "チャットボット管理画面へ遷移" }));

    await waitFor(() => expect(loginWithDevelopmentCpf).toHaveBeenCalledWith({
      role: "staff", display_name: "開発 職員", subject: "staff-001",
    }));
    expect(replace).toHaveBeenCalledWith("/");
  });

  it("必須項目が空の場合は遷移ボタンを無効にする", () => {
    render(<DevelopmentCpfPage />);

    expect(screen.getByRole("button", { name: "チャットボット管理画面へ遷移" }).hasAttribute("disabled")).toBe(true);
  });
});
