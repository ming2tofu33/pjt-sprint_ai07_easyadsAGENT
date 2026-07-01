import { z } from "zod";
export const chatThreadArchiveSchema = z.object({ force: z.boolean().optional() });
