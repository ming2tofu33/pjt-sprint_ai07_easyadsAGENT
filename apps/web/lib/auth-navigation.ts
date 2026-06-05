export const LOGIN_PATH = "/login";
export const APP_HOME_PATH = "/";

const SAFE_AUTH_PATH_PREFIXES = [
  "/admin",
  "/ads",
  "/brand",
  "/generate",
  "/my",
  "/notifications",
  "/onboarding",
  "/reference",
  "/settings",
  "/studio"
] as const;

export function getSafeAuthRedirectPath(value: string | null | undefined, fallback = APP_HOME_PATH): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("://")) {
    return fallback;
  }

  if (value === APP_HOME_PATH) {
    return APP_HOME_PATH;
  }

  const pathname = value.split(/[?#]/, 1)[0] ?? value;
  const isAllowed = SAFE_AUTH_PATH_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));

  return isAllowed ? value : fallback;
}

export function buildLoginHref(nextPath = APP_HOME_PATH): string {
  const safeNext = getSafeAuthRedirectPath(nextPath);
  return `${LOGIN_PATH}?next=${encodeURIComponent(safeNext)}`;
}
