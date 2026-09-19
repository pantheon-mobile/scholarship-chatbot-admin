import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { replace, loginWithDevelopmentCpf, fetchDevelopmentCpfConfig } = vi.hoisted(() => ({
  replace: vi.fn(),
  fetchDevelopmentCpfConfig: vi.fn(),
  loginWithDevelopmentCpf: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("../lib/authApi", () => ({ loginWithDevelopmentCpf, fetchDevelopmentCpfConfig }));

import DevelopmentCpfPage from "../app/development/cpf/DevelopmentCpfForm";

beforeEach(() => {
  replace.mockReset();
  fetchDevelopmentCpfConfig.mockReset().mockResolvedValue({ password_required: false });
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
    await waitFor(() => expect((screen.getByRole("button", { name: "チャットボット管理画面へ遷移" }) as HTMLButtonElement).disabled).toBe(false));
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

it("自社開発環境は共通パスワードを要求してAPIへ渡す", async () => {
  fetchDevelopmentCpfConfig.mockResolvedValue({ password_required: true });
  render(<DevelopmentCpfPage />);
  const password = await screen.findByLabelText("共通パスワード");
  expect(password.getAttribute("type")).toBe("password");
  fireEvent.change(screen.getByLabelText("氏名"), { target: { value: "検証者" } });
  fireEvent.change(screen.getByLabelText("利用者ID"), { target: { value: "tester" } });
  const submit = screen.getByRole("button", { name: "チャットボット管理画面へ遷移" }) as HTMLButtonElement;
  expect(submit.disabled).toBe(true);
  fireEvent.change(password, { target: { value: "shared-test-password" } });
  fireEvent.click(submit);
  await waitFor(() => expect(loginWithDevelopmentCpf).toHaveBeenCalledWith({role:"admin", subject:"tester", display_name:"検証者", password:"shared-test-password"}));
});
