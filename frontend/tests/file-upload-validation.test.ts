import { describe, expect, it } from "vitest";
import { MAX_TOTAL_SIZE, FileSelectionError, validateSelectedFiles } from "@/lib/fileUploadValidation";

function file(name: string, bytes = new Uint8Array([0x61]), type = "text/plain", size?: number) {
  const value = new File([bytes], name, { type });
  Object.defineProperty(value, "arrayBuffer", { value: async () => bytes.buffer });
  if (size !== undefined) Object.defineProperty(value, "size", { value: size });
  return value;
}

describe("CB-203 client file validation", () => {
  it("対応形式と大文字拡張子を受け付ける", async () => {
    const cases = [
      file("a.PDF", new Uint8Array([0x25,0x50,0x44,0x46,0x2d]), "application/pdf"),
      file("a.DOC", new Uint8Array([0xd0,0xcf,0x11,0xe0,0xa1,0xb1,0x1a,0xe1]), "application/msword"),
      file("a.XLS", new Uint8Array([0xd0,0xcf,0x11,0xe0,0xa1,0xb1,0x1a,0xe1]), "application/vnd.ms-excel"),
      file("a.PPT", new Uint8Array([0xd0,0xcf,0x11,0xe0,0xa1,0xb1,0x1a,0xe1]), "application/vnd.ms-powerpoint"),
      file("a.DOCX", new Uint8Array([0x50,0x4b,0x03,0x04]), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
      file("a.XLSX", new Uint8Array([0x50,0x4b,0x03,0x04]), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
      file("a.PPTX", new Uint8Array([0x50,0x4b,0x03,0x04]), "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
      file("a.TXT"), file("a.CSV", new Uint8Array([0x61,0x2c,0x62]), "text/csv"),
    ];
    for (const value of cases) await expect(validateSelectedFiles([], [value])).resolves.toHaveLength(1);
  });

  it.each([
    [file("empty.txt", new Uint8Array()), "EMPTY_FILE"],
    [file("a.md"), "UNSUPPORTED_FILE_TYPE"],
    [file("fake.pdf", new Uint8Array([1,2,3]), "application/pdf"), "FILE_SIGNATURE_MISMATCH"],
  ])("不正ファイルを拒否する", async (value, code) => {
    await expect(validateSelectedFiles([], [value])).rejects.toMatchObject({ code });
  });

  it("同名、21件、100MB超過を拒否する", async () => {
    await expect(validateSelectedFiles([file("same.txt")], [file("SAME.TXT")])).rejects.toMatchObject({ code: "DUPLICATE_FILE_NAME" });
    await expect(validateSelectedFiles([], Array.from({ length: 21 }, (_, index) => file(`${index}.txt`)))).rejects.toMatchObject({ code: "FILE_COUNT_EXCEEDED" });
    await expect(validateSelectedFiles([], [file("large.pdf", new Uint8Array([0x25,0x50,0x44,0x46,0x2d]), "application/pdf", MAX_TOTAL_SIZE + 1)])).rejects.toBeInstanceOf(FileSelectionError);
  });
});
