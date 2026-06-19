export const DEFAULT_BODY_LIMIT_BYTES = 80 * 1024 * 1024;

export function resolveBodyLimitBytes(value) {
  const limit = Number(value);
  return Number.isFinite(limit) && limit > 0 ? limit : DEFAULT_BODY_LIMIT_BYTES;
}

export function getBffConfig(options = {}, env = process.env) {
  return {
    orchestratorBaseUrl: options.orchestratorBaseUrl ?? env.ORCHESTRATOR_BASE_URL ?? "http://127.0.0.1:8000",
    fetchImpl: options.fetchImpl ?? globalThis.fetch,
    supabaseUrl: options.supabaseUrl ?? env.SUPABASE_URL ?? env.NEXT_PUBLIC_SUPABASE_URL,
    supabaseAnonKey: options.supabaseAnonKey ?? env.SUPABASE_ANON_KEY ?? env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    bodyLimitBytes: resolveBodyLimitBytes(options.bodyLimit ?? env.BFF_BODY_LIMIT_BYTES),
    corsOrigin: options.corsOrigin ?? env.CORS_ORIGIN ?? true
  };
}
