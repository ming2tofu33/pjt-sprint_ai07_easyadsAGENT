export const ADMIN_HOME_PATH = "/admin";

export type AdminRole = "owner" | "admin" | "editor";

const ADMIN_ROLES = new Set<AdminRole>(["owner", "admin", "editor"]);

export function isAdminRole(role: unknown): role is AdminRole {
  return typeof role === "string" && ADMIN_ROLES.has(role as AdminRole);
}

export function getSafeAdminRedirectPath(value: string | null | undefined): string {
  if (!value || !value.startsWith("/admin")) {
    return ADMIN_HOME_PATH;
  }

  if (value.startsWith("//") || value.includes("://")) {
    return ADMIN_HOME_PATH;
  }

  return value;
}
