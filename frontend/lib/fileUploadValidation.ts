export const ALLOWED_FILE_EXTENSIONS = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"] as const;
export const FILE_ACCEPT = ALLOWED_FILE_EXTENSIONS.map((extension) => `.${extension}`).join(",");
export const MAX_FILE_COUNT = 20;
export const MAX_TOTAL_SIZE = 100 * 1024 * 1024;

export class FileSelectionError extends Error {
  constructor(public code: string, message: string) { super(message); }
}

const allowedContentTypes: Record<string, string[]> = {
  pdf: ["application/pdf"], doc: ["application/msword"], xls: ["application/vnd.ms-excel"],
  ppt: ["application/vnd.ms-powerpoint"],
  docx: ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
  xlsx: ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
  pptx: ["application/vnd.openxmlformats-officedocument.presentationml.presentation"],
  txt: ["text/plain"], csv: ["text/csv", "application/csv", "application/vnd.ms-excel"],
};

function extensionOf(file: File) { return file.name.split(".").pop()?.toLowerCase() ?? ""; }
function beginsWith(bytes: Uint8Array, signature: number[]) { return signature.every((value, index) => bytes[index] === value); }

async function signatureMatches(file: File, extension: string) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (extension === "pdf") return beginsWith(bytes, [0x25, 0x50, 0x44, 0x46, 0x2d]);
  if (["doc", "xls", "ppt"].includes(extension)) return beginsWith(bytes, [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]);
  if (["docx", "xlsx", "pptx"].includes(extension)) return beginsWith(bytes, [0x50, 0x4b]);
  if (bytes.some((value) => value === 0)) return false;
  for (const encoding of ["utf-8", "shift_jis"]) {
    try { new TextDecoder(encoding, { fatal: true }).decode(bytes); return true; } catch {}
  }
  return false;
}

export async function validateSelectedFiles(existing: File[], incoming: File[]): Promise<File[]> {
  const combined = [...existing, ...incoming];
  if (combined.length > MAX_FILE_COUNT) throw new FileSelectionError("FILE_COUNT_EXCEEDED", "一度に選択できるファイルは20件までです。");
  if (combined.reduce((sum, file) => sum + file.size, 0) > MAX_TOTAL_SIZE) throw new FileSelectionError("TOTAL_SIZE_EXCEEDED", "ファイルの合計サイズは100MB以下にしてください。");
  const names = new Set<string>();
  for (const file of combined) {
    if (file.size === 0) throw new FileSelectionError("EMPTY_FILE", "0バイトのファイルは追加できません。");
    const extension = extensionOf(file);
    if (!(ALLOWED_FILE_EXTENSIONS as readonly string[]).includes(extension)) throw new FileSelectionError("UNSUPPORTED_FILE_TYPE", "対応していないファイル形式です。");
    const normalizedName = file.name.toLocaleLowerCase();
    if (names.has(normalizedName)) throw new FileSelectionError("DUPLICATE_FILE_NAME", "同じ名前のファイルが選択されています。");
    names.add(normalizedName);
    const contentType = file.type.toLowerCase();
    if (contentType && contentType !== "application/octet-stream" && !allowedContentTypes[extension].includes(contentType)) {
      throw new FileSelectionError("FILE_SIGNATURE_MISMATCH", "ファイルの形式と内容が一致していません。");
    }
    if (!(await signatureMatches(file, extension))) throw new FileSelectionError("FILE_SIGNATURE_MISMATCH", "ファイルの形式と内容が一致していません。");
  }
  return combined;
}
