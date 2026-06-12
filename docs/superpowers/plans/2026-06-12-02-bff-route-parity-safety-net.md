# BFF Route Parity Safety Net Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mechanical safety net that shows which FE `/api/*` calls are backed by Next Route Handlers before migrating away from the Fastify BFF.

**Architecture:** Do not migrate routes in this plan. Build a static route parity test that compares `apps/web/lib/api-client.ts`'s known BFF routes with files under `apps/web/app/api`. Keep the test intentionally red until the Next BFF unification plan ports the missing routes, and add a generated markdown inventory for team review.

**Tech Stack:** Next.js App Router file conventions, Vitest, Node `fs/path`, Markdown docs.

---

## File Structure

- Create `apps/web/app/api/_proxy/route-parity.test.ts`: static parity test for required API route files.
- Create `docs/2026-06-12-bff-route-parity-inventory.md`: human-readable inventory of Next-only, Fastify-only, and duplicate routes.
- No production code changes in this plan.

### Task 1: Route Parity Test

**Files:**
- Create: `apps/web/app/api/_proxy/route-parity.test.ts`

- [ ] **Step 1: Write the route parity test**

Create `apps/web/app/api/_proxy/route-parity.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const REQUIRED_NEXT_API_ROUTES = [
  "account/delete",
  "brand-kits",
  "brand-kits/current",
  "brand-kits/[brandKitId]",
  "generated-assets",
  "generation-jobs",
  "generation-jobs/[jobId]",
  "generation-jobs/[jobId]/answer",
  "references",
  "references/[templateId]",
  "references/[templateId]/similar",
  "generate/chat/start",
  "generate/chat/brief",
  "generate/chat/answer",
  "generate/photo/upload",
  "generate/photo/start",
  "assets/uploads/presign",
  "assets/uploads/[assetId]/complete",
  "assets/[assetId]",
  "chat-threads",
  "chat-threads/[threadId]",
  "chat-threads/[threadId]/messages",
  "chat-threads/[threadId]/state",
  "chat-threads/[threadId]/archive",
  "archive/items",
  "archive/items/[archiveItemId]",
  "admin/references",
  "admin/references/[templateId]",
  "admin/references/[templateId]/publish",
  "admin/references/[templateId]/unpublish",
  "references/temp-assets/[removalGroup]/[filename]"
] as const;

const API_ROOT = path.resolve(process.cwd(), "app", "api");

describe("Next BFF route parity", () => {
  it.each(REQUIRED_NEXT_API_ROUTES)("has a route handler for /api/%s", (routePath) => {
    const filePath = path.join(API_ROOT, routePath, "route.ts");
    expect(fs.existsSync(filePath), `missing Next route handler: ${filePath}`).toBe(true);
  });
});
```

- [ ] **Step 2: Run and confirm the expected red state**

Run:

```bash
cd apps/web && npx vitest run app/api/_proxy/route-parity.test.ts
```

Expected: FAIL. Missing routes should include at least `generate/chat/start`, `generate/photo/upload`, `chat-threads`, `archive/items`, and admin references. This red test is the migration checklist.

- [ ] **Step 3: Commit the red guard as explicit migration debt**

```bash
git add apps/web/app/api/_proxy/route-parity.test.ts
git commit -m "test(bff): add Next route parity guard"
```

### Task 2: Human-Readable Route Inventory

**Files:**
- Create: `docs/2026-06-12-bff-route-parity-inventory.md`

- [ ] **Step 1: Generate current Next route list**

Run:

```bash
find apps/web/app/api -path '*/route.ts' -type f | sort
```

Expected: output includes current Next routes such as `apps/web/app/api/generation-jobs/route.ts` and does not include Fastify-only paths like `apps/web/app/api/generate/chat/start/route.ts`.

- [ ] **Step 2: Write the inventory document**

Create `docs/2026-06-12-bff-route-parity-inventory.md`:

```markdown
# BFF Route Parity Inventory

Date: 2026-06-12

## Purpose

This document tracks the migration from the Fastify BFF (`apps/bff`) to Next Route Handlers (`apps/web/app/api`). It exists so the team can see which browser-facing `/api/*` paths are safe on Vercel/same-origin and which still depend on the separate Fastify server.

## Already Present In Next Route Handlers

- `/api/account/delete`
- `/api/brand-kits`
- `/api/brand-kits/current`
- `/api/brand-kits/[brandKitId]`
- `/api/generated-assets`
- `/api/generation-jobs`
- `/api/generation-jobs/[jobId]`
- `/api/generation-jobs/[jobId]/answer`
- `/api/references`
- `/api/references/[templateId]`
- `/api/references/[templateId]/similar`

## Missing From Next Route Handlers

- `/api/generate/chat/start`
- `/api/generate/chat/brief`
- `/api/generate/chat/answer`
- `/api/generate/photo/upload`
- `/api/generate/photo/start`
- `/api/assets/uploads/presign`
- `/api/assets/uploads/[assetId]/complete`
- `/api/assets/[assetId]`
- `/api/chat-threads`
- `/api/chat-threads/[threadId]`
- `/api/chat-threads/[threadId]/messages`
- `/api/chat-threads/[threadId]/state`
- `/api/chat-threads/[threadId]/archive`
- `/api/archive/items`
- `/api/archive/items/[archiveItemId]`
- `/api/admin/references`
- `/api/admin/references/[templateId]`
- `/api/admin/references/[templateId]/publish`
- `/api/admin/references/[templateId]/unpublish`
- `/api/references/temp-assets/[removalGroup]/[filename]`

## Migration Rule

Do not change `NEXT_PUBLIC_BFF_BASE_URL` to same-origin until `apps/web/app/api/_proxy/route-parity.test.ts` is green.
```

- [ ] **Step 3: Commit**

```bash
git add docs/2026-06-12-bff-route-parity-inventory.md
git commit -m "docs(bff): add route parity inventory"
```

## Final Verification

Run:

```bash
cd apps/web && npx vitest run app/api/_proxy/route-parity.test.ts
```

Expected: FAIL until the Next BFF unification plan ports the missing routes. The failure is intentional and should be referenced in the migration PR description.
