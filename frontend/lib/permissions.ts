import { AuthenticatedUser } from "@/types/auth";

export type AdminRole = AuthenticatedUser["role"];

export const systemAdminOnlyPrefixes = [
  "/data-sources",
  "/data-source-types",
  "/categories",
  "/faq-classifications",
  "/usage",
] as const;

export function isSystemAdmin(role: AdminRole): boolean {
  return role === "admin";
}

export function canAccessAdminPath(role: AdminRole, pathname: string): boolean {
  if (role === "student") return false;
  if (role === "admin") return true;
  return !systemAdminOnlyPrefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
