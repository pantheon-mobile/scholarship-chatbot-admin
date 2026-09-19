import { afterEach, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ notFound: () => { throw new Error("NEXT_NOT_FOUND"); } }));
import Page from "../app/development/cpf/page";
afterEach(() => vi.unstubAllEnvs());
it.each(["false", "", undefined])("hides the mock page unless explicitly enabled (%s)", (value) => {
  vi.stubEnv("ENABLE_DEVELOPMENT_CPF_MOCK", value);
  expect(() => Page()).toThrow("NEXT_NOT_FOUND");
});
it("keeps the form for the development environment", () => {
  vi.stubEnv("ENABLE_DEVELOPMENT_CPF_MOCK", "true");
  expect(Page()).toBeTruthy();
});
