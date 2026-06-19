export function internalSecretHeaders(env = process.env) {
  const secret = env.EASYADS_INTERNAL_API_SECRET;
  return secret ? { "X-EasyAds-Internal-Secret": secret } : {};
}

export function verifiedPrincipalHeaders(principal) {
  if (!principal?.userId) return {};
  return {
    "X-EasyAds-User-Id": principal.userId,
    "X-EasyAds-Account-Type": principal.accountType
  };
}
