import Fastify from "fastify";
import cors from "@fastify/cors";

import { getBffConfig, DEFAULT_BODY_LIMIT_BYTES } from "./config.js";
import { registerErrorHandler } from "./errors/error-handler.js";
import { archiveRoutes } from "./routes/archive.js";
import { assetRoutes } from "./routes/assets.js";
import { chatThreadRoutes } from "./routes/chat-threads.js";
import { generationRoutes } from "./routes/generation.js";
import { generationJobRoutes } from "./routes/generation-jobs.js";
import { healthRoutes } from "./routes/health.js";
import { referenceRoutes } from "./routes/references.js";

export { DEFAULT_BODY_LIMIT_BYTES };

export function buildApp(options = {}) {
  const config = getBffConfig(options);
  const app = Fastify({ logger: options.logger ?? false, bodyLimit: config.bodyLimitBytes });

  app.register(cors, { origin: config.corsOrigin });
  registerErrorHandler(app);
  app.register(healthRoutes, { config });
  app.register(referenceRoutes, { config });
  app.register(assetRoutes, { config });
  app.register(chatThreadRoutes, { config });
  app.register(generationRoutes, { config });
  app.register(generationJobRoutes, { config });
  app.register(archiveRoutes, { config });

  return app;
}
