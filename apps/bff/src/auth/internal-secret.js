import { isStrictRuntimeEnv } from "../config.js";

export function internalSecretHeaders(env = process.env) {
  const secret = String(env.EASYADS_INTERNAL_API_SECRET || "").trim();
  if (!secret) {
    if (isStrictRuntimeEnv(env)) {
      throw new Error("EASYADS_INTERNAL_API_SECRET is required in production or staging");
    }
    return {};
  }
  return { "X-EasyAds-Internal-Secret": secret };
}

export function verifiedPrincipalHeaders(principal) {
  if (!principal?.userId) return {};
  return {
    "X-EasyAds-User-Id": principal.userId,
    "X-EasyAds-Account-Type": principal.accountType
  };
}
