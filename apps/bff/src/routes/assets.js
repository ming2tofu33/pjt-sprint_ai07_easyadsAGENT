import { resolveSupabasePrincipal } from "../auth/supabase.js";
import { appendPrincipalQueryParams, proxyGetJson, proxyJson } from "../proxy/orchestrator.js";
import { assetPresignSchema } from "../schemas/assets.js";

export async function assetRoutes(app, { config }) {
  const { fetchImpl, orchestratorBaseUrl, supabaseUrl, supabaseAnonKey } = config;
  const principalFor = (request) => resolveSupabasePrincipal({ request, fetchImpl, supabaseUrl, supabaseAnonKey });
  app.post("/api/assets/uploads/presign", async (request, reply) => {
    const parsed = assetPresignSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    const principal = await principalFor(request);
    return proxyJson({ fetchImpl, url: appendPrincipalQueryParams(`${orchestratorBaseUrl}/api/v1/assets/uploads/presign`, principal), body: parsed.data });
  });
  app.post("/api/assets/uploads/:assetId/complete", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    const principal = await principalFor(request);
    return proxyJson({ fetchImpl, url: appendPrincipalQueryParams(`${orchestratorBaseUrl}/api/v1/assets/uploads/${encodeURIComponent(request.params.assetId)}/complete${query}`, principal), body: {} });
  });
  app.get("/api/assets/:assetId", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    const principal = await principalFor(request);
    return proxyGetJson({ fetchImpl, url: appendPrincipalQueryParams(`${orchestratorBaseUrl}/api/v1/assets/${encodeURIComponent(request.params.assetId)}${query}`, principal) });
  });
}
