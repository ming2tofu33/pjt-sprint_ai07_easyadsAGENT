import { resolveSupabasePrincipal } from "../auth/supabase.js";
import { appendPrincipalQueryParams, proxyDeleteJson, proxyGetJson, proxyJson, proxyPatchJson } from "../proxy/orchestrator.js";
import { archiveItemSchema, archiveItemUpdateSchema, toArchiveItemPayload } from "../schemas/archive.js";

export async function archiveRoutes(app, { config }) {
  const { fetchImpl, orchestratorBaseUrl, supabaseUrl, supabaseAnonKey } = config;
  const principalFor = (request) => resolveSupabasePrincipal({ request, fetchImpl, supabaseUrl, supabaseAnonKey });
  app.get("/api/archive/items", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    return proxyGetJson({ fetchImpl, url: appendPrincipalQueryParams(`${orchestratorBaseUrl}/api/v1/archive/items${query}`, await principalFor(request)) });
  });
  app.post("/api/archive/items", async (request, reply) => {
    const parsed = archiveItemSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    const principal = await principalFor(request);
    const payload = await proxyJson({
      fetchImpl, url: `${orchestratorBaseUrl}/api/v1/archive/items`,
      body: { ...toArchiveItemPayload(parsed.data), ...(principal?.userId ? { user_id: principal.userId } : {}), ...(principal?.accountType ? { account_type: principal.accountType } : {}) }
    });
    return reply.code(201).send(payload);
  });
  app.get("/api/archive/items/:archiveItemId", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    return proxyGetJson({ fetchImpl, url: appendPrincipalQueryParams(`${orchestratorBaseUrl}/api/v1/archive/items/${encodeURIComponent(request.params.archiveItemId)}${query}`, await principalFor(request)) });
  });
  app.patch("/api/archive/items/:archiveItemId", async (request, reply) => {
    const parsed = archiveItemUpdateSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    const principal = await principalFor(request);
    return proxyPatchJson({
      fetchImpl, url: `${orchestratorBaseUrl}/api/v1/archive/items/${encodeURIComponent(request.params.archiveItemId)}`,
      body: { status: parsed.data.status, ...(principal?.userId ? { user_id: principal.userId } : {}), ...(principal?.accountType ? { account_type: principal.accountType } : {}) }
    });
  });
  app.delete("/api/archive/items/:archiveItemId", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    return proxyDeleteJson({ fetchImpl, url: appendPrincipalQueryParams(`${orchestratorBaseUrl}/api/v1/archive/items/${encodeURIComponent(request.params.archiveItemId)}${query}`, await principalFor(request)) });
  });
}
