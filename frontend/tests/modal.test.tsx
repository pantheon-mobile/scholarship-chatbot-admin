import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Modal } from "../components/admin/Modal";

afterEach(cleanup);

function ModalHarness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>削除画面を開く</button>
      <Modal
        open={open}
        title="種別値の削除"
        variant="danger"
        cancelLabel="キャンセル"
        confirmLabel="削除する"
        onConfirm={() => undefined}
        onClose={() => setOpen(false)}
      >
        削除します。
      </Modal>
    </>
  );
}

describe("Modal", () => {
  it("キャンセルに初期フォーカスし、Escで閉じて起動元へフォーカスを戻す", async () => {
    render(<ModalHarness />);
    const trigger = screen.getByRole("button", { name: "削除画面を開く" });
    trigger.focus();
    fireEvent.click(trigger);

    const cancel = screen.getByRole("button", { name: "キャンセル" });
    await waitFor(() => expect(document.activeElement).toBe(cancel));
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("背景クリックで閉じる", () => {
    const onClose = vi.fn();
    render(<Modal open title="確認" onClose={onClose}>本文</Modal>);
    fireEvent.mouseDown(screen.getByRole("presentation"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("dangerではEnterだけで確定しない", () => {
    const onConfirm = vi.fn();
    render(<Modal open title="削除" variant="danger" onConfirm={onConfirm} onClose={() => undefined}>本文</Modal>);
    fireEvent.keyDown(document, { key: "Enter" });
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("処理中はEsc、背景クリック、確定の再送信を無効にする", () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    render(<Modal open busy title="削除" variant="danger" confirmLabel="削除する" onConfirm={onConfirm} onClose={onClose}>本文</Modal>);

    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.mouseDown(screen.getByRole("presentation"));
    fireEvent.click(screen.getByRole("button", { name: "削除する" }));

    expect(onClose).not.toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("TabフォーカスをModal内で循環させる", async () => {
    render(<Modal open title="確認" onConfirm={() => undefined} onClose={() => undefined}>本文</Modal>);
    const cancel = screen.getByRole("button", { name: "キャンセル" });
    const confirm = screen.getByRole("button", { name: "OK" });
    await waitFor(() => expect(document.activeElement).toBe(cancel));

    confirm.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(cancel);

    cancel.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(confirm);
  });

  it("処理失敗時のエラーをModal本文内に表示する", () => {
    render(
      <Modal open title="種別値の削除" variant="danger" error="種別値の削除に失敗しました。" onClose={() => undefined}>
        削除確認本文
      </Modal>,
    );

    expect(screen.getByRole("dialog")).not.toBeNull();
    expect(screen.getByRole("alert").textContent).toBe("種別値の削除に失敗しました。");
  });
});
