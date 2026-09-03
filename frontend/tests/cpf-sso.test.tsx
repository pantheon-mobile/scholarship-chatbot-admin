import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { replace, exchangeCpfToken } = vi.hoisted(() => ({
  replace: vi.fn(),
  exchangeCpfToken: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("../lib/authApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/authApi")>()),
  exchangeCpfToken,
}));

import CpfSsoPage from "../app/sso/cpf/page";
import { CpfExchangeError } from "../lib/authApi";

beforeEach(() => {
  replace.mockReset();
  exchangeCpfToken.mockReset();
  window.history.replaceState(null, "", "/sso/cpf#token=signed-jwt");
});

afterEach(cleanup);

describe("CPF SSO受信", () => {
  it("認証失敗時にBackendが指定したCPF戻り先を表示する", async () => {
    exchangeCpfToken.mockRejectedValue(
      new CpfExchangeError("CPFからもう一度アクセスしてください。", "https://cpf-stg.example/faculty/"),
    );

    render(<CpfSsoPage />);

    expect(await screen.findByText("CPFからもう一度アクセスしてください。")).toBeTruthy();
    expect(screen.getByRole("link", { name: "CPFへ戻る" }).getAttribute("href"))
      .toBe("https://cpf-stg.example/faculty/");
    await waitFor(() => expect(exchangeCpfToken).toHaveBeenCalledWith("signed-jwt"));
    expect(window.location.hash).toBe("");
  });

  it("戻り先未設定時は誤ったトップリンクを表示しない", async () => {
    exchangeCpfToken.mockRejectedValue(new CpfExchangeError("認証に失敗しました。"));

    render(<CpfSsoPage />);

    expect(await screen.findByText("認証に失敗しました。")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
