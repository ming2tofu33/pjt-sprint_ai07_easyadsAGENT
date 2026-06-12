# Next BFF Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move browser-facing BFF behavior from `apps/bff` Fastify into Next Route Handlers so deployed web traffic can use same-origin `/api/*` consistently.

**Architecture:** Extend the existing Next proxy instead of introducing another client. Port Fastify-only routes in batches: proxy capabilities and schemas first, then chat/photo routes, then chat-thread/archive routes, then assets/admin/reference binary routes. Only after route parity is green, switch `apps/web/lib/api-client.ts` to default to same-origin.

**Tech Stack:** Next.js 14 Route Handlers, zod, Supabase verified principal proxying, Vitest, FastAPI orchestrator.

---

## File Structure

- Modify `apps/web/app/api/_proxy/orchestrator.ts`: add DELETE, zod body validation, verified principal query/body injection, binary proxy.
- Create `apps/web/app/api/_schemas/generate.ts`: zod schemas ported from Fastify.
- Create missing `apps/web/app/api/**/route.ts` files.
- Modify `apps/web/lib/api-client.ts`: default BFF base URL to same-origin only after all required Next routes exist.
- Tests in `apps/web/app/api/**` and `apps/web/lib/api-client.test.ts`.

### Task 1: Extend Next Proxy Capabilities

**Files:**
- Modify: `apps/web/app/api/_proxy/orchestrator.ts`
- Test: `apps/web/app/api/_proxy/orchestrator.test.ts`

- [x] **Step 1: Write failing tests**

Add this block to `apps/web/app/api/_proxy/orchestrator.test.ts`:

```ts
it("supports DELETE requests", async () => {
  vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
  const fetchMock = vi.fn(async () => jsonResponse({ success: true }));
  vi.stubGlobal("fetch", fetchMock);

  const request = new NextRequest("http://localhost/api/archive/items/a1", { method: "DELETE" });
  const response = await proxyOrchestratorJson(request, "DELETE", "/api/v1/archive/items/a1");

  expect(response.status).toBe(200);
  expect(fetchMock.mock.calls[0][1]?.method).toBe("DELETE");
});

it("injects verified principal as query params", async () => {
  vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
  vi.stubEnv("SUPABASE_URL", "http://supabase.local");
  vi.stubEnv("SUPABASE_ANON_KEY", "anon");
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse({ id: "guest_uuid_1", is_anonymous: true }))
    .mockResolvedValueOnce(jsonResponse({ threads: [] }));
  vi.stubGlobal("fetch", fetchMock);

  const request = new NextRequest("http://localhost/api/chat-threads?limit=10", {
    headers: { authorization: "Bearer guest_token" }
  });
  await proxyOrchestratorJson(request, "GET", "/api/v1/chat-threads", undefined, {
    injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" }
  });

  const targetUrl = String(fetchMock.mock.calls[1][0]);
  expect(targetUrl).toContain("userId=guest_uuid_1");
  expect(targetUrl).toContain("accountType=guest");
});
```

- [x] **Step 2: Run and verify failure**

Run:

```bash
cd apps/web && npx vitest run app/api/_proxy/orchestrator.test.ts
```

Expected: FAIL because `ProxyMethod` does not include `DELETE` and `injectVerifiedUserIdQuery` is not supported.

- [x] **Step 3: Implement proxy extensions**

In `apps/web/app/api/_proxy/orchestrator.ts`, update types:

```ts
import { z } from "zod";

type ProxyMethod = "GET" | "POST" | "PATCH" | "DELETE";
type PrincipalQueryKeys = {
  userKey: "userId" | "user_id";
  accountKey: "accountType" | "account_type";
};
type ProxyOptions = {
  injectVerifiedUserId?: boolean;
  injectVerifiedUserIdHeader?: boolean;
  injectVerifiedUserIdQuery?: PrincipalQueryKeys;
  injectVerifiedUserIdSnakeBody?: boolean;
  requireNonGuestUser?: boolean;
  bodySchema?: z.ZodTypeAny;
  successStatus?: number;
};
```

Add query injection before `fetch()`:

```ts
let targetUrl = buildTargetUrl(path, request);
if (options.injectVerifiedUserIdQuery) {
  const principal = await getVerifiedPrincipal();
  const url = new URL(targetUrl);
  ["userId", "user_id", "accountType", "account_type"].forEach((key) => url.searchParams.delete(key));
  if (principal) {
    url.searchParams.set(options.injectVerifiedUserIdQuery.userKey, principal.userId);
    url.searchParams.set(options.injectVerifiedUserIdQuery.accountKey, principal.accountType);
  }
  targetUrl = url.toString();
}
```

Add body schema validation immediately after JSON parse:

```ts
let rawPayload = bodyTransform ? bodyTransform(JSON.parse(body)) : JSON.parse(body);
if (options.bodySchema) {
  const parsed = options.bodySchema.safeParse(rawPayload);
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_request", issues: parsed.error.issues }, { status: 400 });
  }
  rawPayload = parsed.data;
}
```

Replace final fetch call:

```ts
const response = await fetch(targetUrl, init);
const payload = await response.json().catch(() => ({}));
const status = response.ok && options.successStatus ? options.successStatus : response.status;
return NextResponse.json(payload, { status });
```

Add binary helper:

```ts
export async function proxyOrchestratorBinary(request: NextRequest, path: string, cacheControl?: string) {
  try {
    const response = await fetch(buildTargetUrl(path, request), { method: "GET", cache: "no-store" });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      return NextResponse.json(payload, { status: response.status });
    }
    const headers = new Headers();
    const contentType = response.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    const resolvedCache = response.headers.get("cache-control") || cacheControl;
    if (resolvedCache) headers.set("cache-control", resolvedCache);
    return new NextResponse(Buffer.from(await response.arrayBuffer()), { status: 200, headers });
  } catch {
    return NextResponse.json(
      { success: false, error_code: "orchestrator_unavailable", message: "Orchestrator API is unavailable." },
      { status: 502 }
    );
  }
}
```

- [x] **Step 4: Run tests**

Run:

```bash
cd apps/web && npx vitest run app/api/_proxy/orchestrator.test.ts
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/web/app/api/_proxy/orchestrator.ts apps/web/app/api/_proxy/orchestrator.test.ts
git commit -m "feat(bff): extend Next orchestrator proxy"
```

### Task 2: Port Shared Zod Schemas

**Files:**
- Create: `apps/web/app/api/_schemas/generate.ts`

- [x] **Step 1: Create schema file**

Create `apps/web/app/api/_schemas/generate.ts`:

```ts
import { z } from "zod";

export const copyGenerationModes = ["suggest_candidates", "auto_pilot", "custom_input", "no_copy"] as const;
export const supportedPhotoMimeTypes = ["image/png", "image/jpeg", "image/webp"] as const;

function requireHeadlineForCustomInput(
  data: { copyGenerationMode?: string; userCustomHeadline?: string },
  context: z.RefinementCtx
) {
  if (data.copyGenerationMode === "custom_input" && !data.userCustomHeadline) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["userCustomHeadline"],
      message: "userCustomHeadline is required for custom_input"
    });
  }
}

const customCopyFields = {
  userCustomHeadline: z.string().trim().min(1).optional(),
  userCustomSubcopy: z.string().trim().optional()
};

const referenceFields = {
  selectedReferenceTemplateId: z.string().trim().min(1).optional(),
  referenceImagePath: z.string().trim().min(1).optional()
};

export const chatStartSchema = z.object({
  userInput: z.string().trim().min(1),
  adFormat: z.string().optional(),
  renderProfile: z.string().optional(),
  copyGenerationMode: z.enum(copyGenerationModes).optional(),
  ...customCopyFields,
  ...referenceFields
}).superRefine(requireHeadlineForCustomInput);

export const chatBriefSchema = z.object({
  jobId: z.string().trim().min(1),
  threadId: z.string().trim().min(1),
  selectedCopyId: z.string().trim().min(1),
  selectedChannelId: z.string().optional(),
  selectedTone: z.string().optional(),
  customDirection: z.string().optional()
});

export const chatAnswerSchema = z.object({
  jobId: z.string().trim().min(1),
  threadId: z.string().trim().min(1),
  field: z.string().trim().min(1),
  value: z.string(),
  customText: z.string().optional()
});

export const photoUploadSchema = z.object({
  filename: z.string().trim().min(1),
  mimeType: z.enum(supportedPhotoMimeTypes),
  dataUrl: z.string().trim().min(1)
});

export const photoStartSchema = z.object({
  userInput: z.string().trim().min(1),
  sourceImagePath: z.string().trim().min(1),
  adFormat: z.string().optional(),
  renderProfile: z.string().optional(),
  copyGenerationMode: z.enum(copyGenerationModes).optional(),
  ...customCopyFields,
  ...referenceFields
}).superRefine(requireHeadlineForCustomInput);

export const archiveItemSchema = z.object({
  title: z.string().trim().min(1),
  publicJobId: z.string().trim().min(1).optional(),
  public_job_id: z.string().trim().min(1).optional(),
  imageUrl: z.string().trim().min(1).optional().nullable(),
  image_url: z.string().trim().min(1).optional().nullable(),
  thumbnailUrl: z.string().trim().min(1).optional().nullable(),
  thumbnail_url: z.string().trim().min(1).optional().nullable(),
  status: z.enum(["saved", "favorite", "failed"]).optional(),
  adFormat: z.string().trim().min(1).optional().nullable(),
  ad_format: z.string().trim().min(1).optional().nullable(),
  platform: z.string().trim().min(1).optional().nullable(),
  source: z.enum(["generated", "reference_template", "uploaded"]).optional(),
  workspaceId: z.string().trim().min(1).optional(),
  workspace_id: z.string().trim().min(1).optional(),
  userId: z.string().trim().min(1).optional(),
  user_id: z.string().trim().min(1).optional(),
  metadata: z.record(z.unknown()).optional()
});

export const archiveItemUpdateSchema = z.object({
  status: z.enum(["saved", "favorite"])
});
```

- [x] **Step 2: Run typecheck**

Run:

```bash
cd apps/web && npx tsc --noEmit
```

Expected: PASS.

- [x] **Step 3: Commit**

```bash
git add apps/web/app/api/_schemas/generate.ts
git commit -m "feat(bff): add shared Next API zod schemas"
```

### Task 3: Port Chat And Photo Start Routes

**Files:**
- Create: `apps/web/app/api/generate/chat/start/route.ts`
- Create: `apps/web/app/api/generate/chat/brief/route.ts`
- Create: `apps/web/app/api/generate/chat/answer/route.ts`
- Create: `apps/web/app/api/generate/photo/start/route.ts`
- Test: `apps/web/app/api/generate/chat/routes.test.ts`

- [x] **Step 1: Write failing route tests**

Create `apps/web/app/api/generate/chat/routes.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
});

describe("generate chat Next routes", () => {
  it("proxies chat start to the legacy marketing chat endpoint", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ jobId: "j1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./start/route");

    const response = await POST(new NextRequest("http://localhost/api/generate/chat/start", {
      method: "POST",
      body: JSON.stringify({ userInput: "카페 광고" })
    }));

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://orchestrator/v1/marketing/chat/start");
  });

  it("rejects custom copy without headline", async () => {
    const { POST } = await import("./start/route");
    const response = await POST(new NextRequest("http://localhost/api/generate/chat/start", {
      method: "POST",
      body: JSON.stringify({ userInput: "광고", copyGenerationMode: "custom_input" })
    }));

    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("invalid_request");
  });
});
```

- [x] **Step 2: Run and verify failure**

Run:

```bash
cd apps/web && npx vitest run app/api/generate/chat/routes.test.ts
```

Expected: FAIL because routes do not exist.

- [x] **Step 3: Implement route handlers**

Create `apps/web/app/api/generate/chat/start/route.ts`:

```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { chatStartSchema } from "../../../_schemas/generate";

export async function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/v1/marketing/chat/start", undefined, {
    bodySchema: chatStartSchema
  });
}
```

Create `apps/web/app/api/generate/chat/brief/route.ts`:

```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { chatBriefSchema } from "../../../_schemas/generate";

export async function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/v1/marketing/chat/brief", undefined, {
    bodySchema: chatBriefSchema
  });
}
```

Create `apps/web/app/api/generate/chat/answer/route.ts`:

```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { chatAnswerSchema } from "../../../_schemas/generate";

export async function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/v1/marketing/chat/answer", undefined, {
    bodySchema: chatAnswerSchema
  });
}
```

Create `apps/web/app/api/generate/photo/start/route.ts`:

```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { photoStartSchema } from "../../../_schemas/generate";

export async function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/v1/marketing/photo/start", undefined, {
    bodySchema: photoStartSchema
  });
}
```

- [x] **Step 4: Run route tests and parity test**

Run:

```bash
cd apps/web && npx vitest run app/api/generate/chat/routes.test.ts app/api/_proxy/route-parity.test.ts
```

Expected: chat route tests PASS; parity still FAILS for remaining missing routes.

- [x] **Step 5: Commit**

```bash
git add apps/web/app/api/generate/chat apps/web/app/api/generate/photo/start apps/web/app/api/generate/chat/routes.test.ts
git commit -m "feat(bff): port chat and photo start routes to Next"
```

### Task 4: Port Chat Thread Routes

**Files:**
- Create: `apps/web/app/api/chat-threads/route.ts`
- Create: `apps/web/app/api/chat-threads/[threadId]/route.ts`
- Create: `apps/web/app/api/chat-threads/[threadId]/messages/route.ts`
- Create: `apps/web/app/api/chat-threads/[threadId]/state/route.ts`
- Create: `apps/web/app/api/chat-threads/[threadId]/archive/route.ts`
- Test: `apps/web/app/api/chat-threads/routes.test.ts`

- [x] **Step 1: Write failing route tests**

Create `apps/web/app/api/chat-threads/routes.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
});

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("chat thread Next routes", () => {
  it("lists threads with verified user query params", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "user_1", is_anonymous: false }))
      .mockResolvedValueOnce(jsonResponse({ threads: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./route");

    const response = await GET(new NextRequest("http://localhost/api/chat-threads?limit=10", {
      headers: { authorization: "Bearer token_1" }
    }));

    expect(response.status).toBe(200);
    const targetUrl = String(fetchMock.mock.calls[1][0]);
    expect(targetUrl).toBe("http://orchestrator/api/v1/chat-threads?limit=10&userId=user_1&accountType=user");
  });

  it("archives a thread through the orchestrator", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ thread: { threadId: "thread_1" } }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./[threadId]/archive/route");

    const response = await POST(
      new NextRequest("http://localhost/api/chat-threads/thread_1/archive", { method: "POST" }),
      { params: { threadId: "thread_1" } }
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://orchestrator/api/v1/chat-threads/thread_1/archive");
  });
});
```

- [x] **Step 2: Run and verify failure**

Run:

```bash
cd apps/web && npx vitest run app/api/chat-threads/routes.test.ts
```

Expected: FAIL because the Next chat-thread routes do not exist.

- [x] **Step 3: Implement route handlers**

Create `apps/web/app/api/chat-threads/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  return proxyOrchestratorJson(request, "GET", "/api/v1/chat-threads", undefined, {
    injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" }
  });
}
```

Create `apps/web/app/api/chat-threads/[threadId]/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(request, "GET", `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}`, undefined, {
    injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" }
  });
}
```

Create `apps/web/app/api/chat-threads/[threadId]/messages/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(
    request,
    "GET",
    `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}/messages`,
    undefined,
    { injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" } }
  );
}
```

Create `apps/web/app/api/chat-threads/[threadId]/state/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(
    request,
    "GET",
    `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}/state`,
    undefined,
    { injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" } }
  );
}
```

Create `apps/web/app/api/chat-threads/[threadId]/archive/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(
    request,
    "POST",
    `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}/archive`,
    undefined,
    { injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" } }
  );
}
```

- [x] **Step 4: Run tests**

Run:

```bash
cd apps/web && npx vitest run app/api/chat-threads/routes.test.ts app/api/_proxy/route-parity.test.ts
```

Expected: chat-thread route tests PASS; parity still FAILS only for routes not ported yet.

- [x] **Step 5: Commit**

```bash
git add apps/web/app/api/chat-threads
git commit -m "feat(bff): port chat thread routes to Next"
```

### Task 5: Port Archive And Upload Routes

**Files:**
- Create: `apps/web/app/api/_schemas/archive.ts`
- Create: `apps/web/app/api/assets/uploads/presign/route.ts`
- Create: `apps/web/app/api/assets/uploads/[assetId]/complete/route.ts`
- Create: `apps/web/app/api/generate/photo/upload/route.ts`
- Create: `apps/web/app/api/archive/items/route.ts`
- Create: `apps/web/app/api/archive/items/[archiveItemId]/route.ts`
- Test: `apps/web/app/api/archive/routes.test.ts`

- [x] **Step 1: Write failing route tests**

Create `apps/web/app/api/archive/routes.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
});

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("archive and upload Next routes", () => {
  it("rejects archive creation without an image url", async () => {
    const { POST } = await import("./items/route");

    const response = await POST(new NextRequest("http://localhost/api/archive/items", {
      method: "POST",
      body: JSON.stringify({ title: "제목만 있음" })
    }));

    expect(response.status).toBe(400);
  });

  it("deletes archive items with DELETE", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);
    const { DELETE } = await import("./items/[archiveItemId]/route");

    const response = await DELETE(
      new NextRequest("http://localhost/api/archive/items/archive_1", { method: "DELETE" }),
      { params: { archiveItemId: "archive_1" } }
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://orchestrator/api/v1/archive/items/archive_1");
  });
});
```

- [x] **Step 2: Run and verify failure**

Run:

```bash
cd apps/web && npx vitest run app/api/archive/routes.test.ts
```

Expected: FAIL because archive routes and schemas do not exist.

- [x] **Step 3: Add archive schema**

Create `apps/web/app/api/_schemas/archive.ts`:

```ts
import { z } from "zod";

export const archiveItemCreateSchema = z.object({
  workspace_id: z.string().optional(),
  workspaceId: z.string().optional(),
  user_id: z.string().optional(),
  userId: z.string().optional(),
  title: z.string().trim().min(1).optional(),
  image_url: z.string().trim().min(1).optional(),
  imageUrl: z.string().trim().min(1).optional(),
  prompt: z.string().optional(),
  metadata: z.record(z.unknown()).optional()
}).superRefine((data, context) => {
  if (!data.image_url && !data.imageUrl) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["imageUrl"],
      message: "imageUrl is required"
    });
  }
});

export const archiveItemUpdateSchema = z.object({
  title: z.string().trim().min(1).optional(),
  metadata: z.record(z.unknown()).optional()
});
```

- [x] **Step 4: Implement archive route handlers**

Create `apps/web/app/api/archive/items/route.ts`:

```ts
import { NextRequest } from "next/server";

import { archiveItemCreateSchema } from "../../_schemas/archive";
import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  return proxyOrchestratorJson(request, "GET", "/api/v1/archive/items", undefined, {
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/archive/items", undefined, {
    bodySchema: archiveItemCreateSchema,
    injectVerifiedUserId: true
  });
}
```

Create `apps/web/app/api/archive/items/[archiveItemId]/route.ts`:

```ts
import { NextRequest } from "next/server";

import { archiveItemUpdateSchema } from "../../../_schemas/archive";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { archiveItemId: string } }) {
  return proxyOrchestratorJson(request, "GET", `/api/v1/archive/items/${encodeURIComponent(params.archiveItemId)}`, undefined, {
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}

export function PATCH(request: NextRequest, { params }: { params: { archiveItemId: string } }) {
  return proxyOrchestratorJson(request, "PATCH", `/api/v1/archive/items/${encodeURIComponent(params.archiveItemId)}`, undefined, {
    bodySchema: archiveItemUpdateSchema,
    injectVerifiedUserId: true
  });
}

export function DELETE(request: NextRequest, { params }: { params: { archiveItemId: string } }) {
  return proxyOrchestratorJson(request, "DELETE", `/api/v1/archive/items/${encodeURIComponent(params.archiveItemId)}`, undefined, {
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}
```

- [x] **Step 5: Implement upload route handlers**

Create `apps/web/app/api/assets/uploads/presign/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/assets/uploads/presign", undefined, {
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}
```

Create `apps/web/app/api/assets/uploads/[assetId]/complete/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest, { params }: { params: { assetId: string } }) {
  return proxyOrchestratorJson(
    request,
    "POST",
    `/api/v1/assets/uploads/${encodeURIComponent(params.assetId)}/complete`,
    undefined,
    { injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" } }
  );
}
```

Create `apps/web/app/api/generate/photo/upload/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/marketing/photo/upload", undefined, {
    injectVerifiedUserId: true
  });
}
```

- [x] **Step 6: Run tests**

Run:

```bash
cd apps/web && npx vitest run app/api/archive/routes.test.ts app/api/_proxy/route-parity.test.ts
```

Expected: archive route tests PASS; parity still FAILS only for routes not ported yet.

- [x] **Step 7: Commit**

```bash
git add apps/web/app/api/_schemas/archive.ts apps/web/app/api/archive apps/web/app/api/assets/uploads apps/web/app/api/generate/photo/upload
git commit -m "feat(bff): port archive and upload routes to Next"
```

### Task 6: Port Binary Asset And Admin Reference Routes

**Files:**
- Create: `apps/web/app/api/assets/[assetId]/route.ts`
- Create: `apps/web/app/api/references/temp-assets/[removalGroup]/[filename]/route.ts`
- Create: `apps/web/app/api/admin/references/route.ts`
- Create: `apps/web/app/api/admin/references/[templateId]/route.ts`
- Create: `apps/web/app/api/admin/references/[templateId]/publish/route.ts`
- Create: `apps/web/app/api/admin/references/[templateId]/unpublish/route.ts`
- Test: `apps/web/app/api/admin/references/routes.test.ts`

- [ ] **Step 1: Write failing route tests**

Create `apps/web/app/api/admin/references/routes.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
});

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("admin reference Next routes", () => {
  it("publishes a reference template", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ template: { id: "ref_1", status: "published" } }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./[templateId]/publish/route");

    const response = await POST(
      new NextRequest("http://localhost/api/admin/references/ref_1/publish", { method: "POST" }),
      { params: { templateId: "ref_1" } }
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://orchestrator/api/v1/admin/references/ref_1/publish");
  });
});
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd apps/web && npx vitest run app/api/admin/references/routes.test.ts
```

Expected: FAIL because admin reference routes do not exist.

- [ ] **Step 3: Implement binary route handlers**

Create `apps/web/app/api/assets/[assetId]/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { assetId: string } }) {
  return proxyOrchestratorJson(request, "GET", `/api/v1/assets/${encodeURIComponent(params.assetId)}`, undefined, {
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}
```

Create `apps/web/app/api/references/temp-assets/[removalGroup]/[filename]/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorBinary } from "../../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(
  request: NextRequest,
  { params }: { params: { removalGroup: string; filename: string } }
) {
  return proxyOrchestratorBinary(
    request,
    `/api/v1/references/temp-assets/${encodeURIComponent(params.removalGroup)}/${encodeURIComponent(params.filename)}`,
    "public, max-age=3600"
  );
}
```

- [ ] **Step 4: Implement admin reference route handlers**

Create `apps/web/app/api/admin/references/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  return proxyOrchestratorJson(request, "GET", "/api/v1/admin/references");
}

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/admin/references", undefined, {
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}
```

Create `apps/web/app/api/admin/references/[templateId]/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function PATCH(request: NextRequest, { params }: { params: { templateId: string } }) {
  return proxyOrchestratorJson(request, "PATCH", `/api/v1/admin/references/${encodeURIComponent(params.templateId)}`);
}
```

Create `apps/web/app/api/admin/references/[templateId]/publish/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest, { params }: { params: { templateId: string } }) {
  return proxyOrchestratorJson(request, "POST", `/api/v1/admin/references/${encodeURIComponent(params.templateId)}/publish`);
}
```

Create `apps/web/app/api/admin/references/[templateId]/unpublish/route.ts`:

```ts
import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest, { params }: { params: { templateId: string } }) {
  return proxyOrchestratorJson(request, "POST", `/api/v1/admin/references/${encodeURIComponent(params.templateId)}/unpublish`);
}
```

- [ ] **Step 5: Run route parity**

Run:

```bash
cd apps/web && npx vitest run app/api/admin/references/routes.test.ts app/api/_proxy/route-parity.test.ts
```

Expected: admin route tests PASS and route parity PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/app/api/assets/[assetId] apps/web/app/api/references/temp-assets apps/web/app/api/admin
git commit -m "feat(bff): port asset and admin reference routes to Next"
```

### Task 7: Switch API Client To Same-Origin After Parity Is Green

**Files:**
- Modify: `apps/web/lib/api-client.ts`
- Test: `apps/web/lib/api-client.test.ts`

- [ ] **Step 1: Write failing test**

Add to `apps/web/lib/api-client.test.ts`:

```ts
it("uses same-origin API routes when NEXT_PUBLIC_BFF_BASE_URL is unset", async () => {
  vi.stubEnv("NEXT_PUBLIC_BFF_BASE_URL", "");
  vi.resetModules();
  const fetchMock = vi.fn(async () =>
    jsonResponse({
      success: true,
      job: {
        job_id: "job_1",
        status: "queued",
        progress: { progress_percent: 0, current_stage: "queued", stage_order: [] },
        metadata: {}
      }
    })
  );
  vi.stubGlobal("fetch", fetchMock);
  const api = await import("./api-client");

  await api.getGenerationJob("job_1");

  expect(String(fetchMock.mock.calls[0][0])).toBe("/api/generation-jobs/job_1");
});
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd apps/web && npx vitest run lib/api-client.test.ts
```

Expected: FAIL because the default is `http://127.0.0.1:4000`.

- [ ] **Step 3: Implement default same-origin**

In `apps/web/lib/api-client.ts`, change:

```ts
const BFF_BASE_URL = normalizeBaseUrl(process.env.NEXT_PUBLIC_BFF_BASE_URL || "http://127.0.0.1:4000");
```

to:

```ts
const BFF_BASE_URL = normalizeBaseUrl(process.env.NEXT_PUBLIC_BFF_BASE_URL || "");
```

- [ ] **Step 4: Run full web validation**

Run:

```bash
cd apps/web && npx vitest run && npx tsc --noEmit
```

Expected: PASS. If route parity is still red, do not merge this task.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/api-client.ts apps/web/lib/api-client.test.ts
git commit -m "feat(bff): default web api client to same-origin"
```

## Final Verification

Run:

```bash
cd apps/web && npx vitest run app/api lib/api-client.test.ts && npx tsc --noEmit
```

Expected: all route tests PASS and `app/api/_proxy/route-parity.test.ts` PASS before disabling Fastify in deployment.
