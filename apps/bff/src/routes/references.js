import { requireSupabaseUserId } from "../auth/supabase.js";
import { appendQueryParam, proxyBinary, proxyGetJson, proxyJson, proxyPatchJson } from "../proxy/orchestrator.js";
import { adminReferenceSchema, adminReferenceUpdateSchema } from "../schemas/references.js";

export async function referenceRoutes(app, { config }) {
  const { fetchImpl, orchestratorBaseUrl, supabaseUrl, supabaseAnonKey } = config;
  const requireUser = (request) => requireSupabaseUserId({ request, fetchImpl, supabaseUrl, supabaseAnonKey });
  app.get("/api/references", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    return proxyGetJson({ fetchImpl, url: `${orchestratorBaseUrl}/api/v1/references${query}` });
  });
  app.get("/api/references/temp-assets/:removalGroup/:filename", async (request, reply) => proxyBinary({
    fetchImpl, url: `${orchestratorBaseUrl}/api/v1/references/temp-assets/${encodeURIComponent(request.params.removalGroup)}/${encodeURIComponent(request.params.filename)}`,
    reply, cacheControl: "public, max-age=604800, immutable"
  }));
  app.get("/api/references/:templateId/similar", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    return proxyGetJson({ fetchImpl, url: `${orchestratorBaseUrl}/api/v1/references/${encodeURIComponent(request.params.templateId)}/similar${query}` });
  });
  app.get("/api/references/:templateId", async (request) => proxyGetJson({ fetchImpl, url: `${orchestratorBaseUrl}/api/v1/references/${encodeURIComponent(request.params.templateId)}` }));
  app.get("/api/admin/references", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    await requireUser(request);
    return proxyGetJson({ fetchImpl, url: `${orchestratorBaseUrl}/api/v1/admin/references${query}` });
  });
  app.post("/api/admin/references", async (request, reply) => {
    const parsed = adminReferenceSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    const userId = await requireUser(request);
    return proxyJson({ fetchImpl, url: appendQueryParam(`${orchestratorBaseUrl}/api/v1/admin/references`, "user_id", userId), body: parsed.data });
  });
  app.patch("/api/admin/references/:templateId", async (request, reply) => {
    const parsed = adminReferenceUpdateSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    await requireUser(request);
    return proxyPatchJson({ fetchImpl, url: `${orchestratorBaseUrl}/api/v1/admin/references/${encodeURIComponent(request.params.templateId)}`, body: parsed.data });
  });
  for (const action of ["publish", "unpublish"]) {
    app.post(`/api/admin/references/:templateId/${action}`, async (request) => {
      await requireUser(request);
      return proxyJson({ fetchImpl, url: `${orchestratorBaseUrl}/api/v1/admin/references/${encodeURIComponent(request.params.templateId)}/${action}`, body: {} });
    });
  }
}
