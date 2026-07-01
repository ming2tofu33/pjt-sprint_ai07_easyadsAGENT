import { createHttpError } from "../errors/http-errors.js";

export function normalizeBearerHeader(value) {
  if (!value) return null;
  const normalized = String(value).trim();
  if (!normalized) return null;
  if (!normalized.toLowerCase().startsWith("bearer ")) {
    throw createHttpError(401, "invalid authorization header");
  }
  return normalized;
}

export async function resolveSupabasePrincipal({ request, fetchImpl, supabaseUrl, supabaseAnonKey }) {
  const authorization = normalizeBearerHeader(request.headers.authorization);
  if (!authorization) return null;
  if (!supabaseUrl || !supabaseAnonKey) {
    throw createHttpError(503, "supabase auth configuration is missing");
  }
  const response = await fetchImpl(`${supabaseUrl.replace(/\/+$/, "")}/auth/v1/user`, {
    method: "GET",
    headers: { accept: "application/json", apikey: supabaseAnonKey, authorization }
  });
  if (!response.ok) throw createHttpError(401, "invalid or expired session");
  const payload = await response.json().catch(() => ({}));
  if (!payload?.id) throw createHttpError(401, "invalid or expired session");
  return { userId: String(payload.id), accountType: payload.is_anonymous ? "guest" : "user" };
}

export async function requireSupabaseUserId(args) {
  const principal = await resolveSupabasePrincipal(args);
  if (!principal?.userId || principal.accountType === "guest") {
    throw createHttpError(401, "admin session required");
  }
  return principal.userId;
}
