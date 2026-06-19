import { resolveSupabasePrincipal } from "../auth/supabase.js";
import { appendPrincipalQueryParams, proxyGetJson, proxyJson } from "../proxy/orchestrator.js";
import { chatThreadArchiveSchema } from "../schemas/chat-threads.js";

export async function chatThreadRoutes(app, { config }) {
  const { fetchImpl, orchestratorBaseUrl, supabaseUrl, supabaseAnonKey } = config;
  const principalFor = (request) => resolveSupabasePrincipal({ request, fetchImpl, supabaseUrl, supabaseAnonKey });
  const target = (path, principal) => appendPrincipalQueryParams(`${orchestratorBaseUrl}${path}`, principal, { userKey: "userId", accountKey: "accountType" });
  app.get("/api/chat-threads", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    return proxyGetJson({ fetchImpl, url: target(`/api/v1/chat-threads${query}`, await principalFor(request)) });
  });
  for (const suffix of ["", "/messages", "/state"]) {
    app.get(`/api/chat-threads/:threadId${suffix}`, async (request) => {
      const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
      return proxyGetJson({ fetchImpl, url: target(`/api/v1/chat-threads/${encodeURIComponent(request.params.threadId)}${suffix}${query}`, await principalFor(request)) });
    });
  }
  app.post("/api/chat-threads/:threadId/archive", async (request) => {
    const parsed = chatThreadArchiveSchema.safeParse(request.body ?? {});
    if (!parsed.success) return { success: false, error: "invalid_request", details: parsed.error.flatten() };
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    return proxyJson({
      fetchImpl, url: target(`/api/v1/chat-threads/${encodeURIComponent(request.params.threadId)}/archive${query}`, await principalFor(request)),
      body: { force: parsed.data.force === true }
    });
  });
  app.post("/api/chat-threads/:threadId/restore", async (request) => {
    const query = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    return proxyJson({ fetchImpl, url: target(`/api/v1/chat-threads/${encodeURIComponent(request.params.threadId)}/restore${query}`, await principalFor(request)), body: {} });
  });
}
