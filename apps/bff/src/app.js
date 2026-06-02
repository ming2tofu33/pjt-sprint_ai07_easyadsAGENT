import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import Fastify from "fastify";
import cors from "@fastify/cors";
import { z } from "zod";

const copyGenerationModes = ["suggest_candidates", "auto_pilot", "custom_input", "no_copy"];
const customCopyFieldsSchema = {
  userCustomHeadline: z.string().trim().min(1).optional(),
  userCustomSubcopy: z.string().trim().optional()
};
const referenceTemplateFieldsSchema = {
  selectedReferenceTemplateId: z.string().trim().min(1).optional()
};

const chatStartSchema = z.object({
  userInput: z.string().min(1),
  adFormat: z.string().optional(),
  renderProfile: z.string().optional(),
  copyGenerationMode: z.enum(copyGenerationModes).optional(),
  ...customCopyFieldsSchema,
  ...referenceTemplateFieldsSchema
}).superRefine((data, context) => {
  if (data.copyGenerationMode === "custom_input" && !data.userCustomHeadline) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["userCustomHeadline"],
      message: "userCustomHeadline is required for custom_input"
    });
  }
});

const chatBriefSchema = z.object({
  jobId: z.string().min(1),
  threadId: z.string().min(1),
  selectedCopyId: z.string().min(1),
  selectedChannelId: z.string().optional(),
  selectedTone: z.string().optional(),
  customDirection: z.string().optional()
});

const chatAnswerSchema = z.object({
  jobId: z.string().min(1),
  threadId: z.string().min(1),
  field: z.string().min(1),
  value: z.string(),
  customText: z.string().optional()
});

const supportedPhotoMimeTypes = ["image/png", "image/jpeg", "image/webp"];
const BFF_SRC_DIR = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_UPLOAD_DIR = path.resolve(BFF_SRC_DIR, "..", "..", "..", "data", "uploads");

const photoUploadSchema = z.object({
  filename: z.string().min(1),
  mimeType: z.enum(supportedPhotoMimeTypes),
  dataUrl: z.string().min(1)
});

const photoStartSchema = z.object({
  userInput: z.string().min(1),
  sourceImagePath: z.string().min(1),
  adFormat: z.string().optional(),
  renderProfile: z.string().optional(),
  copyGenerationMode: z.enum(copyGenerationModes).optional(),
  ...customCopyFieldsSchema,
  ...referenceTemplateFieldsSchema
}).superRefine((data, context) => {
  if (data.copyGenerationMode === "custom_input" && !data.userCustomHeadline) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["userCustomHeadline"],
      message: "userCustomHeadline is required for custom_input"
    });
  }
});

const generationJobSchema = z.object({
  user_input: z.string().optional(),
  userInput: z.string().optional(),
  selected_reference_template_id: z.string().optional(),
  selectedReferenceTemplateId: z.string().optional()
}).passthrough();

async function proxyJson({ fetchImpl, url, body }) {
  const response = await fetchImpl(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.detail?.message || payload?.detail || "orchestrator request failed";
    const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
    error.statusCode = response.status;
    throw error;
  }
  return payload;
}

async function proxyGetJson({ fetchImpl, url }) {
  const response = await fetchImpl(url, {
    method: "GET",
    headers: { accept: "application/json" }
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.detail?.message || payload?.detail || "orchestrator request failed";
    const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
    error.statusCode = response.status;
    throw error;
  }
  return payload;
}

async function proxyBinary({ fetchImpl, url, reply }) {
  const response = await fetchImpl(url, {
    method: "GET"
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = payload?.detail?.message || payload?.detail || "orchestrator request failed";
    const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
    error.statusCode = response.status;
    throw error;
  }
  const contentType = response.headers.get("content-type");
  if (contentType) {
    reply.header("content-type", contentType);
  }
  return Buffer.from(await response.arrayBuffer());
}

function extensionForMimeType(mimeType) {
  if (mimeType === "image/jpeg") {
    return ".jpg";
  }
  if (mimeType === "image/webp") {
    return ".webp";
  }
  return ".png";
}

function decodeDataUrl(dataUrl, mimeType) {
  const prefix = `data:${mimeType};base64,`;
  if (!dataUrl.startsWith(prefix)) {
    const error = new Error("dataUrl mime type does not match mimeType");
    error.statusCode = 400;
    throw error;
  }
  return Buffer.from(dataUrl.slice(prefix.length), "base64");
}

function publicUploadPath(fileName) {
  return `data/uploads/${fileName}`;
}

export function buildApp(options = {}) {
  const app = Fastify({ logger: options.logger ?? false });
  const orchestratorBaseUrl = options.orchestratorBaseUrl ?? process.env.ORCHESTRATOR_BASE_URL ?? "http://127.0.0.1:8000";
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  const uploadDir = options.uploadDir ?? process.env.BFF_UPLOAD_DIR ?? DEFAULT_UPLOAD_DIR;

  app.register(cors, {
    origin: options.corsOrigin ?? process.env.CORS_ORIGIN ?? true
  });

  app.get("/health", async () => ({ status: "ok" }));

  app.get("/api/references", async (request) => {
    const queryString = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
    return proxyGetJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/api/v1/references${queryString}`
    });
  });

  app.get("/api/references/temp-assets/:removalGroup/:filename", async (request, reply) =>
    proxyBinary({
      fetchImpl,
      url: `${orchestratorBaseUrl}/api/v1/references/temp-assets/${encodeURIComponent(request.params.removalGroup)}/${encodeURIComponent(request.params.filename)}`,
      reply
    })
  );

  app.get("/api/references/:templateId", async (request) =>
    proxyGetJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/api/v1/references/${encodeURIComponent(request.params.templateId)}`
    })
  );

  app.post("/api/generate/chat/start", async (request, reply) => {
    const parsed = chatStartSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }

    return proxyJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/v1/marketing/chat/start`,
      body: parsed.data
    });
  });

  app.post("/api/generate/chat/brief", async (request, reply) => {
    const parsed = chatBriefSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }

    return proxyJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/v1/marketing/chat/brief`,
      body: parsed.data
    });
  });

  app.post("/api/generate/chat/answer", async (request, reply) => {
    const parsed = chatAnswerSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }

    return proxyJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/v1/marketing/chat/answer`,
      body: parsed.data
    });
  });

  app.post("/api/generate/photo/upload", async (request, reply) => {
    const parsed = photoUploadSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }

    const imageBuffer = decodeDataUrl(parsed.data.dataUrl, parsed.data.mimeType);
    const extension = extensionForMimeType(parsed.data.mimeType);
    const savedName = `photo_${crypto.randomUUID()}${extension}`;
    await fs.mkdir(uploadDir, { recursive: true });
    await fs.writeFile(path.join(uploadDir, savedName), imageBuffer);

    return {
      sourceImagePath: publicUploadPath(savedName),
      fileName: parsed.data.filename,
      mimeType: parsed.data.mimeType,
      sizeBytes: imageBuffer.length
    };
  });

  app.post("/api/generate/photo/start", async (request, reply) => {
    const parsed = photoStartSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }

    return proxyJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/v1/marketing/photo/start`,
      body: parsed.data
    });
  });

  app.post("/api/generation-jobs", async (request, reply) => {
    const parsed = generationJobSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }
    const body = {
      ...parsed.data,
      selected_reference_template_id: parsed.data.selected_reference_template_id ?? parsed.data.selectedReferenceTemplateId
    };
    delete body.selectedReferenceTemplateId;

    return proxyJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/api/v1/generation-jobs`,
      body
    });
  });

  app.setErrorHandler((error, _request, reply) => {
    reply.code(error.statusCode || 502).send({
      error: "upstream_error",
      message: error.message
    });
  });

  return app;
}
