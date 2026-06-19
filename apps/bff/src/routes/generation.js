import { proxyJson } from "../proxy/orchestrator.js";
import { chatAnswerSchema, chatBriefSchema, chatStartSchema, photoStartSchema, photoUploadSchema } from "../schemas/generation.js";

const invalid = (reply, parsed) => reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });

export async function generationRoutes(app, { config }) {
  const { fetchImpl, orchestratorBaseUrl } = config;
  app.post("/api/generate/chat/start", async (request, reply) => {
    const parsed = chatStartSchema.safeParse(request.body);
    if (!parsed.success) return invalid(reply, parsed);
    return proxyJson({ fetchImpl, url: `${orchestratorBaseUrl}/v1/marketing/chat/start`, body: parsed.data });
  });
  app.post("/api/generate/chat/brief", async (request, reply) => {
    const parsed = chatBriefSchema.safeParse(request.body);
    if (!parsed.success) return invalid(reply, parsed);
    return proxyJson({ fetchImpl, url: `${orchestratorBaseUrl}/v1/marketing/chat/brief`, body: parsed.data });
  });
  app.post("/api/generate/chat/answer", async (request, reply) => {
    const parsed = chatAnswerSchema.safeParse(request.body);
    if (!parsed.success) return invalid(reply, parsed);
    return proxyJson({ fetchImpl, url: `${orchestratorBaseUrl}/v1/marketing/chat/answer`, body: parsed.data });
  });
  app.post("/api/generate/photo/upload", async (request, reply) => {
    const parsed = photoUploadSchema.safeParse(request.body);
    if (!parsed.success) return invalid(reply, parsed);
    return reply.code(410).send({
      error: "legacy_photo_upload_not_supported", error_code: "legacy_photo_upload_not_supported",
      message: "Upload images through the asset presign and complete APIs."
    });
  });
  app.post("/api/generate/photo/start", async (request, reply) => {
    const parsed = photoStartSchema.safeParse(request.body);
    if (!parsed.success) return invalid(reply, parsed);
    return proxyJson({ fetchImpl, url: `${orchestratorBaseUrl}/v1/marketing/photo/start`, body: parsed.data });
  });
}
