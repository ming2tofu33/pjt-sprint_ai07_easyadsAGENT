import { resolveSupabasePrincipal } from "../auth/supabase.js";
import { verifiedPrincipalHeaders } from "../auth/internal-secret.js";
import { proxyGetJson, proxyJson } from "../proxy/orchestrator.js";
import { generationJobAnswerSchema, generationJobSchema } from "../schemas/generation.js";

export async function generationJobRoutes(app, { config }) {
  const { fetchImpl, orchestratorBaseUrl, supabaseUrl, supabaseAnonKey } = config;
  const principalFor = (request) => resolveSupabasePrincipal({ request, fetchImpl, supabaseUrl, supabaseAnonKey });
  app.get("/api/generation-jobs", async (_request, reply) => reply.header("allow", "POST, GET /api/generation-jobs/:jobId").code(405).send({
    error: "generation_job_id_required", error_code: "generation_job_id_required", message: "GET /api/generation-jobs requires a job id."
  }));
  app.post("/api/generation-jobs", async (request, reply) => {
    const parsed = generationJobSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    const principal = await principalFor(request);
    const { userId: _clientUserId, user_id: _clientUserIdSnake, ...clientPayload } = parsed.data;
    const body = {
      ...clientPayload, ...(principal?.userId ? { userId: principal.userId } : {}),
      ...(principal?.accountType ? { accountType: principal.accountType } : {}),
      userInput: parsed.data.userInput ?? parsed.data.user_input, threadId: parsed.data.threadId ?? parsed.data.thread_id,
      selectedReferenceTemplateId: parsed.data.selectedReferenceTemplateId ?? parsed.data.selected_reference_template_id,
      selectedCopyId: parsed.data.selectedCopyId ?? parsed.data.selected_copy_id,
      selectedChannelId: parsed.data.selectedChannelId ?? parsed.data.selected_channel_id,
      selectedTone: parsed.data.selectedTone ?? parsed.data.selected_tone,
      customDirection: parsed.data.customDirection ?? parsed.data.custom_direction,
      userCustomHeadline: parsed.data.userCustomHeadline ?? parsed.data.user_custom_headline,
      userCustomSubcopy: parsed.data.userCustomSubcopy ?? parsed.data.user_custom_subcopy,
      source_asset_id: parsed.data.sourceAssetId ?? parsed.data.source_asset_id,
      reference_asset_id: parsed.data.referenceAssetId ?? parsed.data.reference_asset_id
    };
    for (const key of ["user_input", "thread_id", "selected_reference_template_id", "selected_copy_id", "selected_channel_id", "selected_tone", "custom_direction", "user_custom_headline", "user_custom_subcopy", "sourceAssetId", "referenceAssetId"]) delete body[key];
    return proxyJson({ fetchImpl, url: `${orchestratorBaseUrl}/api/v1/generation-jobs`, body, headers: verifiedPrincipalHeaders(principal) });
  });
  app.get("/api/generation-jobs/:jobId", async (request) => {
    const principal = await principalFor(request);
    return proxyGetJson({ fetchImpl, url: `${orchestratorBaseUrl}/api/v1/generation-jobs/${encodeURIComponent(request.params.jobId)}`, headers: verifiedPrincipalHeaders(principal) });
  });
  app.post("/api/generation-jobs/:jobId/answer", async (request, reply) => {
    const parsed = generationJobAnswerSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    const principal = await principalFor(request);
    const { userId: _clientUserId, user_id: _clientUserIdSnake, ...clientPayload } = parsed.data;
    return proxyJson({
      fetchImpl, url: `${orchestratorBaseUrl}/api/v1/generation-jobs/${encodeURIComponent(request.params.jobId)}/answer`,
      body: { ...clientPayload, ...(principal?.userId ? { userId: principal.userId } : {}) }, headers: verifiedPrincipalHeaders(principal)
    });
  });
}
