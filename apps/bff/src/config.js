export const DEFAULT_BODY_LIMIT_BYTES = 10 * 1024 * 1024;
const STRICT_RUNTIME_ENVS = new Set(["production", "staging"]);

export function isStrictRuntimeEnv(env = process.env) {
  return [
    env.NODE_ENV,
    env.APP_ENV,
    env.VERCEL_ENV,
    env.RAILWAY_ENVIRONMENT,
    env.RAILWAY_ENVIRONMENT_NAME
  ].some((value) => STRICT_RUNTIME_ENVS.has(String(value || "").trim().toLowerCase()));
}

export function resolveBodyLimitBytes(value, mbValue) {
  const limit = Number(value);
  if (Number.isFinite(limit) && limit > 0) return limit;
  const mbLimit = Number(mbValue);
  return Number.isFinite(mbLimit) && mbLimit > 0 ? Math.floor(mbLimit * 1024 * 1024) : DEFAULT_BODY_LIMIT_BYTES;
}

function resolveCorsOrigin(options, env) {
  const origin = options.corsOrigin ?? env.CORS_ORIGIN;
  if (origin) return origin;
  if (isStrictRuntimeEnv(env)) {
    throw new Error("CORS_ORIGIN is required in production or staging");
  }
  return false;
}

function assertStrictInternalSecret(env) {
  if (isStrictRuntimeEnv(env) && !String(env.EASYADS_INTERNAL_API_SECRET || "").trim()) {
    throw new Error("EASYADS_INTERNAL_API_SECRET is required in production or staging");
  }
}

export function getBffConfig(options = {}, env = process.env) {
  assertStrictInternalSecret(env);
  return {
    orchestratorBaseUrl: options.orchestratorBaseUrl ?? env.ORCHESTRATOR_BASE_URL ?? "http://127.0.0.1:8000",
    fetchImpl: options.fetchImpl ?? globalThis.fetch,
    supabaseUrl: options.supabaseUrl ?? env.SUPABASE_URL ?? env.NEXT_PUBLIC_SUPABASE_URL,
    supabaseAnonKey: options.supabaseAnonKey ?? env.SUPABASE_ANON_KEY ?? env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    bodyLimitBytes: resolveBodyLimitBytes(options.bodyLimit ?? env.BFF_BODY_LIMIT_BYTES, env.BFF_BODY_LIMIT_MB),
    corsOrigin: resolveCorsOrigin(options, env)
  };
}
