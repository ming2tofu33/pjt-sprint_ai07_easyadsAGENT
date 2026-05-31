import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";

import Fastify from "fastify";
import cors from "@fastify/cors";
import { z } from "zod";

const chatStartSchema = z.object({
  userInput: z.string().min(1),
  adFormat: z.string().optional(),
  renderProfile: z.string().optional()
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

const photoUploadSchema = z.object({
  filename: z.string().min(1),
  mimeType: z.enum(supportedPhotoMimeTypes),
  dataUrl: z.string().min(1)
});

const photoStartSchema = z.object({
  userInput: z.string().min(1),
  sourceImagePath: z.string().min(1),
  adFormat: z.string().optional(),
  renderProfile: z.string().optional()
});

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
  const uploadDir = options.uploadDir ?? process.env.BFF_UPLOAD_DIR ?? path.resolve(process.cwd(), "../../data/uploads");

  app.register(cors, {
    origin: options.corsOrigin ?? process.env.CORS_ORIGIN ?? true
  });

  app.get("/health", async () => ({ status: "ok" }));

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

  app.setErrorHandler((error, _request, reply) => {
    reply.code(error.statusCode || 502).send({
      error: "upstream_error",
      message: error.message
    });
  });

  return app;
}
