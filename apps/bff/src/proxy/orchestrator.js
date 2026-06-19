import { internalSecretHeaders } from "../auth/internal-secret.js";
import { createUpstreamResponseError, createUpstreamUnavailableError } from "../errors/http-errors.js";

async function proxyJsonMethod({ fetchImpl, url, method, body, headers = {} }) {
  let response;
  try {
    response = await fetchImpl(url, {
      method,
      headers: method === "GET" || method === "DELETE"
        ? { accept: "application/json", ...internalSecretHeaders(), ...headers }
        : { "content-type": "application/json", ...internalSecretHeaders(), ...headers },
      ...(body === undefined ? {} : { body: JSON.stringify(body) })
    });
  } catch (error) {
    throw createUpstreamUnavailableError(url, error);
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw createUpstreamResponseError(url, response, payload);
  return payload;
}

export const proxyJson = (options) => proxyJsonMethod({ ...options, method: "POST" });
export const proxyPatchJson = (options) => proxyJsonMethod({ ...options, method: "PATCH" });
export const proxyDeleteJson = (options) => proxyJsonMethod({ ...options, method: "DELETE" });
export const proxyGetJson = (options) => proxyJsonMethod({ ...options, method: "GET" });

export async function proxyBinary({ fetchImpl, url, reply, cacheControl }) {
  const response = await fetchImpl(url, { method: "GET", headers: internalSecretHeaders() });
  const payload = response.ok ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw createUpstreamResponseError(url, response, payload);
  const contentType = response.headers.get("content-type");
  if (contentType) reply.header("content-type", contentType);
  const responseCacheControl = response.headers.get("cache-control") || cacheControl;
  if (responseCacheControl) reply.header("cache-control", responseCacheControl);
  return Buffer.from(await response.arrayBuffer());
}

export function appendQueryParam(url, key, value) {
  if (!url.includes("?")) return value ? `${url}?${encodeURIComponent(key)}=${encodeURIComponent(value)}` : url;
  const [base, queryStr] = url.split("?", 2);
  const params = new URLSearchParams(queryStr);
  if (key === "userId" || key === "user_id") {
    params.delete("userId"); params.delete("user_id");
  }
  if (key === "accountType" || key === "account_type") {
    params.delete("accountType"); params.delete("account_type");
  }
  if (value) params.set(key, value);
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}

export function appendPrincipalQueryParams(url, principal, { userKey = "user_id", accountKey = "account_type" } = {}) {
  return appendQueryParam(appendQueryParam(url, userKey, principal?.userId ?? null), accountKey, principal?.accountType ?? null);
}
