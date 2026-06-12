# FE/BFF/BE 구조 개선 구현 계획 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `FE_BFF_BE_LOGIC_MAP.md`에서 확정한 P1~P10 구조 문제를 5개 독립 Phase로 해소 — BFF 단일화, URL 빌더 타입 안전화, ChatGenerateClient 분해, FE↔BE 계약 고정, BE 내구성/문서 정리.

**Architecture:** Phase별로 독립 배포 가능하게 설계함. Phase 1(BFF 단일화)이 최우선 — Fastify `apps/bff` 전용 엔드포인트 14개를 Next.js Route Handlers로 이식 후 base URL을 same-origin으로 전환, Fastify 폐기. Phase 3(god component 분해)은 Phase 1 완료 후 진행(어느 BFF로 가는지 고민 제거된 상태에서). 각 Phase 내 Task는 2~5분 단위, TDD, 작은 커밋.

**Tech Stack:** Next.js 14 App Router Route Handlers, zod, Vitest + Testing Library, FastAPI, LangGraph(SqliteSaver), TypeScript `tsc --noEmit`.

**선행 조건/규칙:**
- 작업 디렉터리: `/home/spai0722/codeit`
- 커밋은 작성자 본인이 직접 함 (Claude/Codex는 커밋 금지 — 커밋 step은 "사용자가 커밋" 의미)
- 공유 파일(`ChatGenerateClient.tsx`) 작업 전 `git status`/`git pull` 확인 — 멀티 에이전트 동시 편집 환경임
- 각 Phase 끝마다 검증 게이트: `cd apps/web && npx vitest run && npx tsc --noEmit`
- Phase는 순서 권장이지만 1↔2는 병행 가능, 3은 1 완료 후, 4/5는 독립

---

## Phase 0: 안전망 (선행, ~30분)

이식 전 현재 동작을 고정하는 가드 테스트. 이게 있어야 Phase 1에서 빠뜨린 엔드포인트를 기계적으로 잡음.

### Task 0.1: BFF 라우트 패리티 테스트

**Files:**
- Create: `apps/web/app/api/_proxy/route-parity.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성**

api-client가 호출하는 모든 `/api/*` 경로가 Next route handler 파일로 존재하는지 검사. 지금은 14개가 없으므로 실패해야 정상.

```ts
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

// api-client.ts가 호출하는 BFF 경로 전수 (FE_BFF_BE_LOGIC_MAP.md 3-1절 기준)
const REQUIRED_BFF_PATHS = [
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
  "references",
  "references/[templateId]",
  "references/[templateId]/similar",
  "references/temp-assets/[removalGroup]/[filename]",
  "generation-jobs",
  "generation-jobs/[jobId]",
  "generation-jobs/[jobId]/answer",
  "brand-kits",
  "brand-kits/current",
  "brand-kits/[brandKitId]",
  "generated-assets",
  "account/delete"
];

const API_DIR = path.resolve(__dirname, "..");

describe("BFF route parity", () => {
  it.each(REQUIRED_BFF_PATHS)("has Next route handler for /api/%s", (relPath) => {
    const routeFile = path.join(API_DIR, relPath, "route.ts");
    expect(fs.existsSync(routeFile), `missing ${routeFile}`).toBe(true);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd /home/spai0722/codeit/apps/web && npx vitest run app/api/_proxy/route-parity.test.ts`
Expected: FAIL — `generate/chat/start` 등 14개 항목에서 `missing …/route.ts`

- [ ] **Step 3: 커밋 (사용자)**

```bash
git add apps/web/app/api/_proxy/route-parity.test.ts
git commit -m "test: add BFF route parity guard (red until Fastify routes ported)"
```

---

## Phase 1: BFF 단일화 — Next Route Handlers로 통일 (P3, P5, P7, P9)

**전략:** Fastify(`apps/bff/src/app.js`)에만 있는 엔드포인트를 전부 `apps/web/app/api/*`로 이식 → `api-client.ts` 기본 base를 same-origin(`""`)으로 전환 → Fastify는 1 사이클 검증 후 폐기. 이식 중 동작 기준은 **현재 Fastify 구현과 byte-level 동등** (스키마/쿼리 주입/에러 포맷 동일).

**⚠️ 결정 필요 (구현 전 사용자 확인 1건):** `POST /api/generate/photo/upload`는 Fastify가 로컬 디스크(`data/uploads/`)에 파일을 씀. Vercel 서버리스에선 디스크가 휘발됨. 선택지:
- (a) 로컬/도커 배포 전제로 동일 이식 (아래 Task 1.6은 (a) 기준으로 작성)
- (b) 기존 `POST /api/assets/uploads/presign` R2 경로로 FE를 마이그레이션하고 photo/upload 폐기
(b)가 정답이지만 FE `uploadPhotoAsset` 호출부 수정이 필요해 범위 커짐. Phase 1에선 (a)로 패리티 확보, (b)는 후속 이슈로 분리 권장.

### Task 1.1: 프록시 공용 모듈 확장

**Files:**
- Modify: `apps/web/app/api/_proxy/orchestrator.ts`
- Test: `apps/web/app/api/_proxy/orchestrator.test.ts` (기존 파일에 추가)

- [ ] **Step 1: 실패하는 테스트 작성** (기존 test 파일 하단에 추가)

```ts
describe("proxyOrchestratorJson extensions", () => {
  it("supports DELETE method", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/archive/items/a1", { method: "DELETE" });
    const response = await proxyOrchestratorJson(request, "DELETE", "/api/v1/archive/items/a1");
    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
  });

  it("injects verified principal as query params when injectVerifiedUserIdQuery is set", async () => {
    // Supabase /auth/v1/user 200 + orchestrator 200 순서로 응답
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "user-1", is_anonymous: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    process.env.SUPABASE_URL = "http://supabase.local";
    process.env.SUPABASE_ANON_KEY = "anon";
    const request = new NextRequest("http://localhost/api/chat-threads", {
      headers: { authorization: "Bearer token-1" }
    });
    await proxyOrchestratorJson(request, "GET", "/api/v1/chat-threads", undefined, {
      injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" }
    });
    const targetUrl = String(fetchMock.mock.calls[1][0]);
    expect(targetUrl).toContain("userId=user-1");
    expect(targetUrl).toContain("accountType=user");
  });

  it("rejects with 400 when bodySchema validation fails", async () => {
    const request = new NextRequest("http://localhost/api/generate/chat/start", {
      method: "POST",
      body: JSON.stringify({}) // userInput 누락
    });
    const response = await proxyOrchestratorJson(request, "POST", "/v1/marketing/chat/start", undefined, {
      bodySchema: z.object({ userInput: z.string().min(1) })
    });
    expect(response.status).toBe(400);
    const payload = await response.json();
    expect(payload.error).toBe("invalid_request");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run app/api/_proxy/orchestrator.test.ts`
Expected: FAIL — `DELETE` not assignable to `ProxyMethod`, unknown option keys

- [ ] **Step 3: 구현**

`orchestrator.ts` 변경점 (기존 코드 유지 + 아래 확장):

```ts
import { z } from "zod";

type ProxyMethod = "GET" | "POST" | "PATCH" | "DELETE";
type PrincipalQueryKeys = { userKey: "userId" | "user_id"; accountKey: "accountType" | "account_type" };
type ProxyOptions = {
  injectVerifiedUserId?: boolean;
  injectVerifiedUserIdHeader?: boolean;
  injectVerifiedUserIdQuery?: PrincipalQueryKeys;   // NEW: Fastify appendPrincipalQueryParams 대응
  requireAdminUser?: boolean;                       // NEW: Fastify requireSupabaseUserId 대응
  bodySchema?: z.ZodTypeAny;                        // NEW: Fastify zod safeParse 대응
  successStatus?: number;                           // NEW: archive POST 201 대응
};
```

`proxyOrchestratorJson` 본문 수정 (try 블록 앞부분):

```ts
    if (options.requireAdminUser) {
      const principal = await getVerifiedPrincipal();
      if (!principal?.userId || principal.accountType === "guest") {
        throw proxyError("admin session required", 401, "admin_session_required");
      }
    }
```

`buildTargetUrl` 호출부를 principal query 주입 가능하게 교체:

```ts
    let targetUrl = buildTargetUrl(path, request);
    if (options.injectVerifiedUserIdQuery) {
      const principal = await getVerifiedPrincipal();
      const url = new URL(targetUrl);
      const { userKey, accountKey } = options.injectVerifiedUserIdQuery;
      // 클라이언트가 보낸 위조 가능한 값 제거 후 검증된 값으로 교체
      ["userId", "user_id"].forEach((k) => url.searchParams.delete(k));
      ["accountType", "account_type"].forEach((k) => url.searchParams.delete(k));
      if (principal?.userId) {
        url.searchParams.set(userKey, principal.userId);
        url.searchParams.set(accountKey, principal.accountType);
      }
      targetUrl = url.toString();
    }
```

body 처리부에 zod 검증 삽입 (`JSON.parse(body)` 직후):

```ts
        if (options.bodySchema) {
          const parsed = options.bodySchema.safeParse(rawPayload);
          if (!parsed.success) {
            return NextResponse.json(
              { error: "invalid_request", issues: parsed.error.issues },
              { status: 400 }
            );
          }
          rawPayload = parsed.data;
        }
```

응답부: `return NextResponse.json(payload, { status: options.successStatus ?? response.status });`
(주의: `successStatus`는 upstream 2xx일 때만 적용 — `response.ok ? options.successStatus ?? response.status : response.status`)

바이너리 프록시 함수 신규 추가 (temp-assets, assets 서빙용):

```ts
export async function proxyOrchestratorBinary(
  request: NextRequest,
  path: string,
  cacheControl?: string
): Promise<NextResponse> {
  try {
    const response = await fetch(buildTargetUrl(path, request), { method: "GET", cache: "no-store" });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      return NextResponse.json(payload, { status: response.status });
    }
    const headers = new Headers();
    const contentType = response.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    const upstreamCache = response.headers.get("cache-control") || cacheControl;
    if (upstreamCache) headers.set("cache-control", upstreamCache);
    return new NextResponse(Buffer.from(await response.arrayBuffer()), { status: 200, headers });
  } catch {
    return NextResponse.json(
      { success: false, error_code: "orchestrator_unavailable", message: "Orchestrator API is unavailable." },
      { status: 502 }
    );
  }
}
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run app/api/_proxy/orchestrator.test.ts`
Expected: PASS (기존 + 신규 전부)

- [ ] **Step 5: 커밋 (사용자)**

```bash
git add apps/web/app/api/_proxy/orchestrator.ts apps/web/app/api/_proxy/orchestrator.test.ts
git commit -m "feat(bff): extend Next proxy with DELETE/principal-query/zod/binary support"
```

### Task 1.2: zod 스키마 공용 파일 생성

**Files:**
- Create: `apps/web/app/api/_schemas/generate.ts`

- [ ] **Step 1: Fastify 스키마를 그대로 이식** (`apps/bff/src/app.js:10~167` 출처 — 동작 동일성 위해 1:1 복사, 리팩터 금지)

```ts
import { z } from "zod";

export const copyGenerationModes = ["suggest_candidates", "auto_pilot", "custom_input", "no_copy"] as const;

const customCopyFields = {
  userCustomHeadline: z.string().trim().min(1).optional(),
  userCustomSubcopy: z.string().trim().optional()
};
const referenceTemplateFields = { selectedReferenceTemplateId: z.string().trim().min(1).optional() };
const referenceImageFields = { referenceImagePath: z.string().trim().min(1).optional() };

function requireHeadlineForCustomInput(data: { copyGenerationMode?: string; userCustomHeadline?: string }, context: z.RefinementCtx) {
  if (data.copyGenerationMode === "custom_input" && !data.userCustomHeadline) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["userCustomHeadline"],
      message: "userCustomHeadline is required for custom_input"
    });
  }
}

export const chatStartSchema = z.object({
  userInput: z.string().min(1),
  adFormat: z.string().optional(),
  renderProfile: z.string().optional(),
  copyGenerationMode: z.enum(copyGenerationModes).optional(),
  ...customCopyFields,
  ...referenceTemplateFields,
  ...referenceImageFields
}).superRefine(requireHeadlineForCustomInput);

export const chatBriefSchema = z.object({
  jobId: z.string().min(1),
  threadId: z.string().min(1),
  selectedCopyId: z.string().min(1),
  selectedChannelId: z.string().optional(),
  selectedTone: z.string().optional(),
  customDirection: z.string().optional()
});

export const chatAnswerSchema = z.object({
  jobId: z.string().min(1),
  threadId: z.string().min(1),
  field: z.string().min(1),
  value: z.string(),
  customText: z.string().optional()
});

export const supportedPhotoMimeTypes = ["image/png", "image/jpeg", "image/webp"] as const;

export const photoUploadSchema = z.object({
  filename: z.string().min(1),
  mimeType: z.enum(supportedPhotoMimeTypes),
  dataUrl: z.string().min(1)
});

export const photoStartSchema = z.object({
  userInput: z.string().min(1),
  sourceImagePath: z.string().min(1),
  adFormat: z.string().optional(),
  renderProfile: z.string().optional(),
  copyGenerationMode: z.enum(copyGenerationModes).optional(),
  ...customCopyFields,
  ...referenceTemplateFields,
  ...referenceImageFields
}).superRefine(requireHeadlineForCustomInput);

export const assetPresignSchema = z.object({
  kind: z.enum(["upload", "source", "reference"]),
  filename: z.string().trim().min(1),
  mimeType: z.enum(supportedPhotoMimeTypes),
  sizeBytes: z.number().int().positive(),
  workspaceId: z.string().trim().min(1).optional(),
  threadId: z.string().trim().min(1).optional()
});

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

export const archiveItemUpdateSchema = z.object({ status: z.enum(["saved", "favorite"]) });

export const adminReferenceSchema = z.object({
  templateId: z.string().trim().min(1).optional(),
  assetId: z.string().trim().min(1),
  workspaceId: z.string().trim().min(1).optional(),
  title: z.string().trim().min(1),
  description: z.string().optional().nullable(),
  category: z.string().trim().min(1),
  subCategory: z.string().optional().nullable(),
  tags: z.array(z.string()).optional(),
  businessTypes: z.array(z.string()).optional(),
  adFormats: z.array(z.string()).optional(),
  platforms: z.array(z.string()).optional(),
  aspectRatio: z.string().optional().nullable(),
  styleKeywords: z.array(z.string()).optional(),
  colorPalette: z.array(z.string()).optional(),
  layoutHint: z.string().optional().nullable(),
  typographyHint: z.string().optional().nullable(),
  backgroundStyle: z.string().optional().nullable(),
  popularityScore: z.number().min(0).optional(),
  status: z.enum(["active", "inactive", "draft"]).optional(),
  licenseNote: z.string().optional().nullable(),
  copyrightStatus: z.string().optional(),
  metadata: z.record(z.unknown()).optional()
});

export const adminReferenceUpdateSchema = adminReferenceSchema.omit({ assetId: true, workspaceId: true }).partial();
```

- [ ] **Step 2: 타입 확인**

Run: `npx tsc --noEmit`
Expected: EXIT 0

- [ ] **Step 3: 커밋 (사용자)**

```bash
git add apps/web/app/api/_schemas/generate.ts
git commit -m "feat(bff): port Fastify zod schemas to Next API layer"
```

### Task 1.3: chat 생성 플로우 라우트 3개 이식

**Files:**
- Create: `apps/web/app/api/generate/chat/start/route.ts`
- Create: `apps/web/app/api/generate/chat/brief/route.ts`
- Create: `apps/web/app/api/generate/chat/answer/route.ts`
- Test: `apps/web/app/api/generate/chat/routes.test.ts`

주의: BE prefix가 `/v1/marketing/chat/*` (P7 — `/api/v1` 아님). 이식 시 그대로 유지하고, prefix 통일은 Phase 5에서 BE와 함께 처리.

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

beforeEach(() => vi.unstubAllGlobals());

describe("generate/chat routes", () => {
  it("start proxies valid payload to /v1/marketing/chat/start", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ jobId: "j1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./start/route");
    const request = new NextRequest("http://localhost/api/generate/chat/start", {
      method: "POST",
      body: JSON.stringify({ userInput: "카페 광고" })
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toContain("/v1/marketing/chat/start");
  });

  it("start rejects custom_input without headline (400, zod parity with Fastify)", async () => {
    const { POST } = await import("./start/route");
    const request = new NextRequest("http://localhost/api/generate/chat/start", {
      method: "POST",
      body: JSON.stringify({ userInput: "x", copyGenerationMode: "custom_input" })
    });
    const response = await POST(request);
    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("invalid_request");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run app/api/generate/chat/routes.test.ts`
Expected: FAIL — `Cannot find module './start/route'`

- [ ] **Step 3: 구현 (3개 파일, 전체 코드)**

`start/route.ts`:
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

`brief/route.ts`:
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

`answer/route.ts`:
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

- [ ] **Step 4: 통과 확인 + 패리티 테스트 진척 확인**

Run: `npx vitest run app/api/generate/chat/routes.test.ts app/api/_proxy/route-parity.test.ts`
Expected: routes.test PASS, parity는 chat 3개 항목 green (나머지 still red)

- [ ] **Step 5: 커밋 (사용자)**

```bash
git add apps/web/app/api/generate/chat apps/web/app/api/_schemas
git commit -m "feat(bff): port chat start/brief/answer routes to Next"
```

### Task 1.4: chat-threads 라우트 5개 이식

**Files:**
- Create: `apps/web/app/api/chat-threads/route.ts`
- Create: `apps/web/app/api/chat-threads/[threadId]/route.ts`
- Create: `apps/web/app/api/chat-threads/[threadId]/messages/route.ts`
- Create: `apps/web/app/api/chat-threads/[threadId]/state/route.ts`
- Create: `apps/web/app/api/chat-threads/[threadId]/archive/route.ts`
- Test: `apps/web/app/api/chat-threads/routes.test.ts`

Fastify 원본은 principal을 **camelCase 쿼리**(`userId`/`accountType`)로 주입함 — Task 1.1의 `injectVerifiedUserIdQuery` 옵션 사용.

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

beforeEach(() => vi.unstubAllGlobals());

describe("chat-threads routes", () => {
  it("list injects verified principal as camelCase query", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "u1", is_anonymous: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ threads: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    process.env.SUPABASE_URL = "http://supabase.local";
    process.env.SUPABASE_ANON_KEY = "anon";
    const { GET } = await import("./route");
    const request = new NextRequest("http://localhost/api/chat-threads?limit=10", {
      headers: { authorization: "Bearer t" }
    });
    await GET(request);
    const url = String(fetchMock.mock.calls[1][0]);
    expect(url).toContain("/api/v1/chat-threads");
    expect(url).toContain("userId=u1");
    expect(url).toContain("accountType=guest");
    expect(url).toContain("limit=10");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run app/api/chat-threads/routes.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: 구현 (5개 파일 전체)**

`route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../_proxy/orchestrator";

const PRINCIPAL_QUERY = { userKey: "userId", accountKey: "accountType" } as const;

export async function GET(request: NextRequest) {
  return proxyOrchestratorJson(request, "GET", "/api/v1/chat-threads", undefined, {
    injectVerifiedUserIdQuery: PRINCIPAL_QUERY
  });
}
```

`[threadId]/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export async function GET(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(request, "GET", `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}`, undefined, {
    injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" }
  });
}
```

`[threadId]/messages/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export async function GET(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(
    request, "GET", `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}/messages`, undefined,
    { injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" } }
  );
}
```

`[threadId]/state/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export async function GET(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(
    request, "GET", `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}/state`, undefined,
    { injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" } }
  );
}
```

`[threadId]/archive/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export async function POST(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(
    request, "POST", `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}/archive`, undefined,
    { injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" } }
  );
}
```

- [ ] **Step 4: 통과 확인** — `npx vitest run app/api/chat-threads/routes.test.ts` → PASS

- [ ] **Step 5: 커밋 (사용자)** — `git commit -m "feat(bff): port chat-threads routes to Next"`

### Task 1.5: archive 라우트 이식 (GET/POST 목록 + GET/PATCH/DELETE 항목)

**Files:**
- Create: `apps/web/app/api/archive/items/route.ts`
- Create: `apps/web/app/api/archive/items/[archiveItemId]/route.ts`
- Test: `apps/web/app/api/archive/routes.test.ts`

주의 3가지 (Fastify 원본 `app.js:756~829` 동작):
1. 목록/항목 GET, DELETE는 principal을 **snake_case 쿼리**(`user_id`/`account_type`)로 주입
2. POST/PATCH는 principal을 **body**에 `user_id`/`account_type`으로 주입 — 기존 proxy의 `injectVerifiedUserId`는 camelCase(`userId`)를 쓰므로 그대로 못 씀. snake 주입 옵션 필요: Task 1.1의 `ProxyOptions`에 `injectVerifiedUserIdSnakeBody?: boolean` 추가하고 body 주입 분기에서 `payload.user_id = principal.userId; payload.account_type = principal.accountType;` 사용 (camel 키 4종 delete 동일).
3. POST는 `toArchiveItemPayload` camel→snake 변환 + 201 응답 — `bodyTransform` + `successStatus: 201` 사용.

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

beforeEach(() => vi.unstubAllGlobals());

describe("archive routes", () => {
  it("POST converts camelCase payload to snake_case and returns 201", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./items/route");
    const request = new NextRequest("http://localhost/api/archive/items", {
      method: "POST",
      body: JSON.stringify({ title: "내 광고", publicJobId: "job1", imageUrl: "/img.png" })
    });
    const response = await POST(request);
    expect(response.status).toBe(201);
    const sentBody = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(sentBody.public_job_id).toBe("job1");
    expect(sentBody.image_url).toBe("/img.png");
    expect(sentBody.status).toBe("saved");
    expect(sentBody.publicJobId).toBeUndefined();
  });
});
```

- [ ] **Step 2: 실패 확인** — `npx vitest run app/api/archive/routes.test.ts` → FAIL module not found

- [ ] **Step 3: 구현**

`items/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../_proxy/orchestrator";
import { archiveItemSchema } from "../../_schemas/generate";

function compactObject(value: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined && item !== null));
}

export function toArchiveItemPayload(data: Record<string, unknown>) {
  return compactObject({
    title: data.title,
    public_job_id: data.public_job_id ?? data.publicJobId,
    image_url: data.image_url ?? data.imageUrl,
    thumbnail_url: data.thumbnail_url ?? data.thumbnailUrl,
    status: data.status ?? "saved",
    ad_format: data.ad_format ?? data.adFormat,
    platform: data.platform,
    source: data.source,
    workspace_id: data.workspace_id ?? data.workspaceId,
    metadata: data.metadata
  });
}

export async function GET(request: NextRequest) {
  return proxyOrchestratorJson(request, "GET", "/api/v1/archive/items", undefined, {
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}

export async function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/archive/items", toArchiveItemPayload, {
    bodySchema: archiveItemSchema,
    injectVerifiedUserIdSnakeBody: true,
    successStatus: 201
  });
}
```

`items/[archiveItemId]/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { archiveItemUpdateSchema } from "../../../_schemas/generate";

type Params = { params: { archiveItemId: string } };
const SNAKE_QUERY = { userKey: "user_id", accountKey: "account_type" } as const;

export async function GET(request: NextRequest, { params }: Params) {
  return proxyOrchestratorJson(
    request, "GET", `/api/v1/archive/items/${encodeURIComponent(params.archiveItemId)}`, undefined,
    { injectVerifiedUserIdQuery: SNAKE_QUERY }
  );
}

export async function PATCH(request: NextRequest, { params }: Params) {
  return proxyOrchestratorJson(
    request, "PATCH", `/api/v1/archive/items/${encodeURIComponent(params.archiveItemId)}`, undefined,
    { bodySchema: archiveItemUpdateSchema, injectVerifiedUserIdSnakeBody: true }
  );
}

export async function DELETE(request: NextRequest, { params }: Params) {
  return proxyOrchestratorJson(
    request, "DELETE", `/api/v1/archive/items/${encodeURIComponent(params.archiveItemId)}`, undefined,
    { injectVerifiedUserIdQuery: SNAKE_QUERY }
  );
}
```

(Task 1.1 proxy에 `injectVerifiedUserIdSnakeBody` 옵션 추가가 빠졌다면 이 시점에 추가 — body 주입 분기 코드:)
```ts
        if (options.injectVerifiedUserIdSnakeBody && payload && typeof payload === "object" && !Array.isArray(payload)) {
          delete (payload as Record<string, unknown>).user_id;
          delete (payload as Record<string, unknown>).userId;
          delete (payload as Record<string, unknown>).account_type;
          delete (payload as Record<string, unknown>).accountType;
          const principal = await getVerifiedPrincipal();
          if (principal) {
            (payload as Record<string, unknown>).user_id = principal.userId;
            (payload as Record<string, unknown>).account_type = principal.accountType;
          }
        }
```

- [ ] **Step 4: 통과 확인** — `npx vitest run app/api/archive` → PASS
- [ ] **Step 5: 커밋 (사용자)** — `git commit -m "feat(bff): port archive item routes to Next"`

### Task 1.6: photo upload/start + assets 라우트 이식

**Files:**
- Create: `apps/web/app/api/generate/photo/upload/route.ts`
- Create: `apps/web/app/api/generate/photo/start/route.ts`
- Create: `apps/web/app/api/assets/uploads/presign/route.ts`
- Create: `apps/web/app/api/assets/uploads/[assetId]/complete/route.ts`
- Create: `apps/web/app/api/assets/[assetId]/route.ts`
- Test: `apps/web/app/api/generate/photo/routes.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

beforeEach(() => vi.unstubAllGlobals());

describe("photo upload route", () => {
  it("writes decoded image to upload dir and returns sourceImagePath", async () => {
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "easyads-upload-"));
    process.env.BFF_UPLOAD_DIR = tmpDir;
    const { POST } = await import("./upload/route");
    const pngBase64 = Buffer.from("fakepng").toString("base64");
    const request = new NextRequest("http://localhost/api/generate/photo/upload", {
      method: "POST",
      body: JSON.stringify({
        filename: "p.png",
        mimeType: "image/png",
        dataUrl: `data:image/png;base64,${pngBase64}`
      })
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload.sourceImagePath).toMatch(/^data\/uploads\/photo_.+\.png$/);
    expect(payload.sizeBytes).toBe(7);
    const files = await fs.readdir(tmpDir);
    expect(files).toHaveLength(1);
  });

  it("rejects mime/dataUrl mismatch with 400", async () => {
    const { POST } = await import("./upload/route");
    const request = new NextRequest("http://localhost/api/generate/photo/upload", {
      method: "POST",
      body: JSON.stringify({ filename: "p.png", mimeType: "image/png", dataUrl: "data:image/jpeg;base64,AAAA" })
    });
    const response = await POST(request);
    expect(response.status).toBe(400);
  });
});
```

- [ ] **Step 2: 실패 확인** — FAIL module not found

- [ ] **Step 3: 구현**

`upload/route.ts` (Fastify `app.js:640~659` 동작 1:1 — ⚠️ 서버리스 배포 시 디스크 휘발, Phase 1 헤더의 결정 (a)/(b) 참고):
```ts
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { photoUploadSchema } from "../../../_schemas/generate";

export const runtime = "nodejs";

const DEFAULT_UPLOAD_DIR = path.resolve(process.cwd(), "..", "..", "data", "uploads");

function extensionForMimeType(mimeType: string): string {
  if (mimeType === "image/jpeg") return ".jpg";
  if (mimeType === "image/webp") return ".webp";
  return ".png";
}

export async function POST(request: NextRequest) {
  const parsed = photoUploadSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid_request", issues: parsed.error.issues }, { status: 400 });
  }
  const { filename, mimeType, dataUrl } = parsed.data;
  const prefix = `data:${mimeType};base64,`;
  if (!dataUrl.startsWith(prefix)) {
    return NextResponse.json({ error: "invalid_request", message: "dataUrl mime type does not match mimeType" }, { status: 400 });
  }
  const imageBuffer = Buffer.from(dataUrl.slice(prefix.length), "base64");
  const savedName = `photo_${crypto.randomUUID()}${extensionForMimeType(mimeType)}`;
  const uploadDir = process.env.BFF_UPLOAD_DIR || DEFAULT_UPLOAD_DIR;
  await fs.mkdir(uploadDir, { recursive: true });
  await fs.writeFile(path.join(uploadDir, savedName), imageBuffer);
  return NextResponse.json({
    sourceImagePath: `data/uploads/${savedName}`,
    fileName: filename,
    mimeType,
    sizeBytes: imageBuffer.length
  });
}
```

`start/route.ts`:
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

`assets/uploads/presign/route.ts` (Fastify는 snake 쿼리로 principal 주입):
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { assetPresignSchema } from "../../../_schemas/generate";

export async function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/assets/uploads/presign", undefined, {
    bodySchema: assetPresignSchema,
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}
```

`assets/uploads/[assetId]/complete/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../../_proxy/orchestrator";

export async function POST(request: NextRequest, { params }: { params: { assetId: string } }) {
  return proxyOrchestratorJson(
    request, "POST", `/api/v1/assets/uploads/${encodeURIComponent(params.assetId)}/complete`, undefined,
    { injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" } }
  );
}
```

`assets/[assetId]/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export async function GET(request: NextRequest, { params }: { params: { assetId: string } }) {
  return proxyOrchestratorJson(
    request, "GET", `/api/v1/assets/${encodeURIComponent(params.assetId)}`, undefined,
    { injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" } }
  );
}
```

- [ ] **Step 4: 통과 확인** — `npx vitest run app/api/generate/photo` → PASS
- [ ] **Step 5: 커밋 (사용자)** — `git commit -m "feat(bff): port photo upload/start and asset routes to Next"`

### Task 1.7: admin references + temp-assets 바이너리 라우트 이식

**Files:**
- Create: `apps/web/app/api/admin/references/route.ts`
- Create: `apps/web/app/api/admin/references/[templateId]/route.ts`
- Create: `apps/web/app/api/admin/references/[templateId]/publish/route.ts`
- Create: `apps/web/app/api/admin/references/[templateId]/unpublish/route.ts`
- Create: `apps/web/app/api/references/temp-assets/[removalGroup]/[filename]/route.ts`
- Test: `apps/web/app/api/admin/references/routes.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성** (admin gate가 핵심 — guest 401)

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

beforeEach(() => vi.unstubAllGlobals());

describe("admin references routes", () => {
  it("rejects guest principal with 401", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "u1", is_anonymous: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    process.env.SUPABASE_URL = "http://supabase.local";
    process.env.SUPABASE_ANON_KEY = "anon";
    const { GET } = await import("./route");
    const request = new NextRequest("http://localhost/api/admin/references", {
      headers: { authorization: "Bearer t" }
    });
    const response = await GET(request);
    expect(response.status).toBe(401);
  });
});
```

- [ ] **Step 2: 실패 확인** — FAIL module not found

- [ ] **Step 3: 구현**

`admin/references/route.ts` (POST는 검증된 user_id를 쿼리로 — Fastify `appendQueryParam(url, "user_id", userId)` 동작):
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../_proxy/orchestrator";
import { adminReferenceSchema } from "../../_schemas/generate";

export async function GET(request: NextRequest) {
  return proxyOrchestratorJson(request, "GET", "/api/v1/admin/references", undefined, {
    requireAdminUser: true
  });
}

export async function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/admin/references", undefined, {
    requireAdminUser: true,
    bodySchema: adminReferenceSchema,
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}
```

`admin/references/[templateId]/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { adminReferenceUpdateSchema } from "../../../_schemas/generate";

export async function PATCH(request: NextRequest, { params }: { params: { templateId: string } }) {
  return proxyOrchestratorJson(
    request, "PATCH", `/api/v1/admin/references/${encodeURIComponent(params.templateId)}`, undefined,
    { requireAdminUser: true, bodySchema: adminReferenceUpdateSchema }
  );
}
```

`publish/route.ts` / `unpublish/route.ts` (둘 다 동일 패턴, 경로만 다름):
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorJson } from "../../../../_proxy/orchestrator";

export async function POST(request: NextRequest, { params }: { params: { templateId: string } }) {
  return proxyOrchestratorJson(
    request, "POST", `/api/v1/admin/references/${encodeURIComponent(params.templateId)}/publish`, undefined,
    { requireAdminUser: true }
  );
}
```
(unpublish는 위 코드에서 경로 끝 `/publish` → `/unpublish`만 변경)

`references/temp-assets/[removalGroup]/[filename]/route.ts`:
```ts
import { NextRequest } from "next/server";
import { proxyOrchestratorBinary } from "../../../../_proxy/orchestrator";

export async function GET(
  request: NextRequest,
  { params }: { params: { removalGroup: string; filename: string } }
) {
  return proxyOrchestratorBinary(
    request,
    `/api/v1/references/temp-assets/${encodeURIComponent(params.removalGroup)}/${encodeURIComponent(params.filename)}`,
    "public, max-age=604800, immutable"
  );
}
```

- [ ] **Step 4: 패리티 게이트 전체 통과 확인**

Run: `npx vitest run app/api`
Expected: **route-parity.test.ts 전 항목 PASS** + 신규 route 테스트 전부 PASS

- [ ] **Step 5: 커밋 (사용자)** — `git commit -m "feat(bff): port admin references and temp-assets routes; full route parity"`

### Task 1.8: api-client base URL same-origin 전환

**Files:**
- Modify: `apps/web/lib/api-client.ts:16` (BFF_BASE_URL 정의)
- Modify: `apps/web/next.config.mjs` (이미지 remotePatterns — same-origin이면 불필요해짐)
- Test: `apps/web/lib/api-client.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성** (api-client.test.ts에 추가)

```ts
it("builds same-origin URL when NEXT_PUBLIC_BFF_BASE_URL is unset", async () => {
  vi.stubEnv("NEXT_PUBLIC_BFF_BASE_URL", "");
  vi.resetModules();
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  const api = await import("./api-client");
  await api.getGenerationJob("j1");
  expect(String(fetchMock.mock.calls[0][0])).toBe("/api/generation-jobs/j1");
});
```

- [ ] **Step 2: 실패 확인** — 현재 기본값 `http://127.0.0.1:4000`이 붙어 FAIL

- [ ] **Step 3: 구현**

```ts
// before
const BFF_BASE_URL = normalizeBaseUrl(process.env.NEXT_PUBLIC_BFF_BASE_URL || "http://127.0.0.1:4000");
// after — 기본 same-origin (빈 문자열). 외부 BFF가 필요한 환경만 env로 지정.
const BFF_BASE_URL = normalizeBaseUrl(process.env.NEXT_PUBLIC_BFF_BASE_URL || "");
```

`next.config.mjs`: `bffRemotePattern()`이 빈 base URL에서 `new URL("")` throw → catch로 null 반환하므로 동작엔 문제 없음. 단 same-origin 이미지엔 remotePatterns 자체가 불필요 — 함수와 사용처 삭제하고 `images: {}` 로 정리.

- [ ] **Step 4: 전체 검증**

Run: `npx vitest run && npx tsc --noEmit`
Expected: 전부 PASS / EXIT 0

- [ ] **Step 5: 수동 스모크 (필수)**

```bash
# 터미널 1: orchestrator
cd /home/spai0722/codeit && uv run uvicorn orchestrator.app.api.app:create_app --factory --port 8000
# 터미널 2: web (Fastify :4000 안 띄움!)
cd apps/web && npm run dev
```
브라우저: `/generate/chat` 진입 → 채팅 입력 → 브리프 → 최종 생성 → 완료 화면. Fastify 없이 전 플로우 동작하면 성공.
Expected: 생성 완료 화면 + 네트워크 탭에서 모든 호출이 same-origin `/api/*`

- [ ] **Step 6: 커밋 (사용자)** — `git commit -m "feat(bff): default api-client to same-origin Next routes"`

### Task 1.9: Fastify BFF 폐기 준비 (삭제는 별도 사이클)

**Files:**
- Modify: `docker-compose.yml`, `Makefile` (bff 서비스/타깃 주석 처리 + deprecated 표기)
- Modify: `apps/bff/src/app.js` 기동 로그에 deprecation 경고 1줄
- Create: `/home/spai0722/BFF_DEPRECATION_NOTE.md` (팀 공지용, 한국어)

- [ ] **Step 1:** docker-compose의 bff 서비스에 `# DEPRECATED 2026-06: Next app/api로 통합됨. 1 release 검증 후 삭제 예정.` 주석. Makefile bff 타깃 동일.
- [ ] **Step 2:** 팀 공지 md 작성 — 전환 일자, 롤백 방법(`NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000` 재설정), 삭제 예정일.
- [ ] **Step 3:** 검증 1 사이클(팀 합의 기간) 후 후속 PR에서 `apps/bff/` 디렉터리 + Phase 0 패리티 테스트의 Fastify 의존 부분 삭제. **이 계획서 범위 밖 — 별도 세션.**
- [ ] **Step 4: 커밋 (사용자)** — `git commit -m "chore(bff): mark Fastify BFF deprecated after Next migration"`

---

## Phase 2: URL 빌더 타입 안전화 (P4) — 작고 독립적, Phase 1과 병행 가능

### Task 2.1: jobId 필요 stage를 타입으로 차단

**Files:**
- Modify: `apps/web/lib/dashboard-navigation.ts`
- Test: `apps/web/lib/dashboard-navigation.test.ts` (route-builders.test.ts 패턴 참고)

근거: #6 버그 직접 원인 = `buildDashboardHref("chat","generating")`이 jobId 없는 URL 생성. `generating`/`complete`는 jobId 없이 의미가 없으므로 컴파일 타임에 차단.

- [ ] **Step 1: 실패하는 테스트 작성** (타입 테스트 + 런타임 가드)

```ts
import { describe, expect, it } from "vitest";
import { buildDashboardHref } from "./dashboard-navigation";

describe("buildDashboardHref jobId-required stages", () => {
  it("throws on chat+generating without job context (must use buildChatStageHrefForJob)", () => {
    // @ts-expect-error — generating은 JobBoundStage라 buildDashboardHref에 못 들어가야 함
    expect(() => buildDashboardHref("chat", "generating")).toThrow(/job-bound stage/);
  });

  it("still builds plain stages", () => {
    expect(buildDashboardHref("chat", "start")).toBe("/generate/chat");
  });
});
```

- [ ] **Step 2: 실패 확인** — `@ts-expect-error`가 "unused"로 컴파일 에러 + 런타임 not throw → FAIL

- [ ] **Step 3: 구현** (`dashboard-navigation.ts`)

```ts
export const jobBoundStages = ["generating", "complete"] as const;
export type JobBoundStage = (typeof jobBoundStages)[number];
export type FreeStage = Exclude<DashboardStage, JobBoundStage>;

const jobBoundStageSet = new Set<string>(jobBoundStages);

// 시그니처 변경: stage 파라미터에서 JobBoundStage 제외
export function buildDashboardHref(surface: DashboardSurface, stage?: FreeStage): string {
  if (surface === "chat" && stage && jobBoundStageSet.has(stage)) {
    throw new Error(`buildDashboardHref: "${stage}" is a job-bound stage; use buildChatStageHrefForJob(stage, job) instead.`);
  }
  // …기존 본문 그대로…
}
```

- [ ] **Step 4: 컴파일 깨지는 호출부 전수 수정**

Run: `npx tsc --noEmit 2>&1 | grep dashboard-navigation`
나오는 모든 호출부를 검토 — jobId 보유 문맥이면 `buildChatStageHrefForJob`로 교체, 아니면 로직 오류이므로 `setGenerationStage` 로컬 전환으로 교체(#6 수정과 동일 패턴). 호출부 grep:

```bash
grep -rn 'buildDashboardHref("chat", *"\(generating\|complete\)")' apps/web --include="*.ts*" | grep -v node_modules
```
Expected: 0건이 될 때까지 수정 (#6 수정으로 핵심 1곳은 이미 제거됨)

- [ ] **Step 5: 전체 검증 + 커밋 (사용자)**

Run: `npx vitest run && npx tsc --noEmit` → PASS
```bash
git commit -m "feat(nav): make job-bound stages unrepresentable in buildDashboardHref"
```

---

## Phase 3: ChatGenerateClient 분해 (P1, P2) — Phase 1 완료 후

**전략:** 한 번에 다 쪼개지 않음. 3단계 점진 추출 — (a) 비-chat surface 페이지 독립 → (b) 스냅샷/복원 로직을 훅·lib으로 추출 → (c) 상태 single source of truth 정리. 각 단계마다 기존 80개 테스트 green 유지가 게이트. **이 Phase 동안 `ChatGenerateClient.tsx`는 단독 작업 영역으로 선언 (Codex와 동시 작업 금지 — #5/#6 때 합의한 영역 분리 원칙).**

### Task 3.1: 스냅샷 IO를 lib으로 추출 (동작 무변경 move)

**Files:**
- Create: `apps/web/lib/chat-snapshots.ts`
- Create: `apps/web/lib/chat-snapshots.test.ts`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx` (대략 :160~290 — `readChatTurnSnapshot`/`writeChatFlowSnapshot`/`clearGenerationFailureSnapshot` 등 storage 헬퍼 일체)

- [ ] **Step 1:** ChatGenerateClient.tsx 상단의 sessionStorage/localStorage 헬퍼 함수 전부(스토리지 키 상수 포함)를 `lib/chat-snapshots.ts`로 **그대로 이동** (수정 금지, import만 정리). 함수 목록은 이동 직전 `grep -n "sessionStorage\|localStorage" ChatGenerateClient.tsx`로 확정.
- [ ] **Step 2:** 이동한 각 함수에 단위 테스트 작성 — 키별 round-trip + JSON 파손 시 null 반환:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { readChatTurnSnapshot, writeChatTurnSnapshot, clearChatTurnSnapshot } from "./chat-snapshots";

beforeEach(() => sessionStorage.clear());

describe("chat-snapshots", () => {
  it("round-trips a turn snapshot", () => {
    writeChatTurnSnapshot({ prompt: "p", response: { jobId: "j", threadId: "t" } } as never);
    expect(readChatTurnSnapshot()?.prompt).toBe("p");
    clearChatTurnSnapshot();
    expect(readChatTurnSnapshot()).toBeNull();
  });

  it("returns null on corrupted JSON", () => {
    sessionStorage.setItem("easyads_chat_turn_snapshot_v1", "{broken");
    expect(readChatTurnSnapshot()).toBeNull();
  });
});
```
(실제 키 이름·타입은 이동한 코드의 상수를 그대로 사용 — 추측 금지)

- [ ] **Step 3:** 검증 — `npx vitest run app/generate/chat lib/chat-snapshots.test.ts && npx tsc --noEmit` → 80개 + 신규 전부 PASS
- [ ] **Step 4: 커밋 (사용자)** — `git commit -m "refactor(chat): extract snapshot storage IO to lib/chat-snapshots"`

### Task 3.2: 비-chat surface 페이지 독립 (studio/reference/ads)

**Files:**
- Create: `apps/web/app/generate/SurfaceShell.tsx` (얇은 공용 셸: MobileShell + toast + navigateTo)
- Modify: `apps/web/app/studio/page.tsx`, `apps/web/app/reference/page.tsx`, `apps/web/app/ads/page.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx` (해당 surface 분기 제거)
- Test: 기존 `ChatGenerateClient.test.tsx` 중 studio/reference/ads 시나리오를 신규 컴포넌트 테스트로 이전

- [ ] **Step 1:** ChatGenerateClient 내 `appSurface === "studio" | "reference" | "ads"` 분기가 렌더하는 Step 컴포넌트와 그에 필요한 상태(archive: `generatedCreatives`, `archiveLoadState`, `archiveReloadToken` → `useArchiveCreatives` 훅으로 추출)를 식별:

```bash
grep -n 'appSurface === "studio"\|appSurface === "reference"\|appSurface === "ads"' apps/web/app/generate/chat/ChatGenerateClient.tsx
```

- [ ] **Step 2:** `useArchiveCreatives` 훅 추출 (`apps/web/lib/use-archive-creatives.ts`) — ChatGenerateClient의 archive 로딩 useEffect + 3개 state를 그대로 이동:

```ts
import { useEffect, useState } from "react";
import type { MockCreative } from "@/lib/mock-dashboard-data";

export type ArchiveLoadState = "idle" | "loading" | "loaded" | "error";

export function useArchiveCreatives() {
  const [creatives, setCreatives] = useState<MockCreative[]>([]);
  const [loadState, setLoadState] = useState<ArchiveLoadState>("idle");
  const [reloadToken, setReloadToken] = useState(0);
  // ChatGenerateClient의 archive 로딩 useEffect 본문을 그대로 이동
  // (이동 시점에 grep으로 정확한 effect 위치 재확인: grep -n "archiveLoadState" ChatGenerateClient.tsx)
  const reload = () => setReloadToken((token) => token + 1);
  return { creatives, loadState, reload, setCreatives, reloadToken };
}
```

- [ ] **Step 3:** 3개 page.tsx를 surface별 컴포넌트로 교체. 예 `app/ads/page.tsx`:

```tsx
import { AdsSurfacePage } from "@/app/generate/AdsSurfacePage";

export default function AdsPage() {
  return <AdsSurfacePage />;
}
```
`AdsSurfacePage`는 SurfaceShell + RecentAdsStep + useArchiveCreatives 조합 (기존 ChatGenerateClient 분기 JSX를 그대로 이식).

- [ ] **Step 4:** ChatGenerateClient에서 해당 분기 + 이제 미사용된 state/handler 삭제. `dashboardSurfaces` 타입은 유지(네비게이션 호환).
- [ ] **Step 5:** 테스트 이전 — `ChatGenerateClient.test.tsx`에서 studio/ads/reference 렌더 검증 테스트를 `AdsSurfacePage.test.tsx` 등으로 이동, 나머지 chat/photo 테스트 green 확인.

Run: `npx vitest run app/generate && npx tsc --noEmit`
Expected: PASS (총 테스트 수 동일 이상)

- [ ] **Step 6: 수동 스모크** — `/studio`, `/reference`, `/ads` 진입 + 거기서 `/generate/chat`으로 네비게이션 왕복.
- [ ] **Step 7: 커밋 (사용자)** — `git commit -m "refactor(surfaces): split studio/reference/ads out of ChatGenerateClient"`

### Task 3.3: 복원 useEffect를 단일 책임 훅 3개로 분해

**Files:**
- Create: `apps/web/app/generate/chat/useChatRouteRestore.ts`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx` (거대 복원 effect :1041~1265 — 정확 범위는 작업 시점 grep으로 재확정)
- Test: `apps/web/app/generate/chat/useChatRouteRestore.test.tsx` (renderHook)

분해 기준 (현 effect가 섞고 있는 3가지 관심사):
1. **잡 복원**: URL `jobId` 존재 → `getGenerationJob` 조회 → stage 결정
2. **스레드 복원**: URL `threadId` 존재 → thread state/messages 조회 → reducer 복원
3. **stage priming**: `initialStage` prop → `generationStage` 초기 동기화 (lastPrimedStageRef 가드)

- [ ] **Step 1: 가드 테스트 먼저** — 현 동작(특히 #5/#6 회귀 테스트) green 상태에서 시작 확인: `npx vitest run app/generate/chat/ChatGenerateClient.test.tsx` → PASS
- [ ] **Step 2:** `useChatRouteRestore` 훅 시그니처 정의 + effect 본문을 관심사별 3개 useEffect로 분리해 훅 내부로 이동:

```ts
export type ChatRouteRestoreInput = {
  initialStage: DashboardStage;
  jobIdParam: string | null;
  threadIdParam: string | null;
  dispatch: Dispatch<ChatFlowAction>;
  setGenerationStage: (stage: GenerationStage) => void;
};

export function useChatRouteRestore(input: ChatRouteRestoreInput): void {
  // effect 1: stage priming — deps: [input.initialStage]만. jobIdParam 의존 금지.
  // effect 2: job restore — deps: [input.jobIdParam]. jobId 없으면 아무것도 안 함(fallback 렌더 금지 — #6 재발 방지 불변식).
  // effect 3: thread restore — deps: [input.threadIdParam].
}
```

핵심 불변식 (코드 주석으로 박제): **jobId 부재는 "아직 도착 안 함"일 수 있으므로 절대 실패/완료 화면으로 fallback하지 않는다.** (#5/#6 공통 원인)

- [ ] **Step 3:** renderHook 테스트 — jobIdParam null→값 전이 시 stage가 complete로 튀지 않음을 검증:

```tsx
it("does not flash complete stage while jobIdParam is still null", async () => {
  const setGenerationStage = vi.fn();
  const { rerender } = renderHook(
    ({ jobIdParam }) => useChatRouteRestore({ initialStage: "generating", jobIdParam, threadIdParam: null, dispatch: vi.fn(), setGenerationStage }),
    { initialProps: { jobIdParam: null as string | null } }
  );
  expect(setGenerationStage).not.toHaveBeenCalledWith("complete");
  rerender({ jobIdParam: "job-1" });
  // job fetch mock 완료 대기 후에만 stage 전환 허용
});
```

- [ ] **Step 4:** ChatGenerateClient에서 거대 effect 삭제, 훅 호출 1줄로 교체. `lastPrimedStageRef`는 훅 내부로 이동.
- [ ] **Step 5:** 전체 검증 — `npx vitest run app/generate/chat && npx tsc --noEmit` → 기존 80개(특히 #5/#6 회귀 테스트) 전부 PASS
- [ ] **Step 6: 커밋 (사용자)** — `git commit -m "refactor(chat): split restore mega-effect into single-concern hooks"`

### Task 3.4: optimisticSurface 제거 — URL을 surface의 single source of truth로

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`

전제: Task 3.2 후 ChatGenerateClient가 chat/photo만 담당 → surface 전환은 전부 라우터 이동. `setOptimisticSurface`는 페이지 이동 전 깜빡임 방지용이었으나, surface별 페이지 분리 후엔 Next 라우팅(자체 pending UI)으로 충분.

- [ ] **Step 1:** `optimisticSurface` state + `appSurface` 파생 제거, `initialSurface` prop 직접 사용. `navigateTo`에서 `setOptimisticSurface(surface)` 줄 삭제.
- [ ] **Step 2:** #6 수정에서 넣었던 `setOptimisticSurface("chat")` 호출부는 chat surface 내부 전환이므로 이제 no-op — 삭제하고 주석 갱신.
- [ ] **Step 3:** 검증 — 전체 suite + 수동: `/generate/chat` 흐름에서 surface 깜빡임 없는지, #6 플래시 재발 없는지 (회귀 테스트가 잡아줌).
- [ ] **Step 4: 커밋 (사용자)** — `git commit -m "refactor(chat): make URL the single source of truth for surface"`

---

## Phase 4: FE↔BE 계약 고정 (P6) — 독립 실행 가능

### Task 4.1: 생성 stage 이름 계약 fixture

**Files:**
- Create: `apps/web/types/contracts/generation-stages.json`
- Create: `orchestrator/tests/test_generation_stage_contract.py`
- Test: `apps/web/lib/generation-job-stage.contract.test.ts`

- [ ] **Step 1:** BE의 stage 이름 출처 확정:

```bash
grep -rn "current_stage" /home/spai0722/codeit/orchestrator/app --include="*.py" | grep -v test | head -20
```
Expected: stage 문자열을 set/enum으로 정의한 모듈 1곳 (예: `generation_jobs/execution.py`). 산재해 있으면 먼저 상수 모듈로 모으는 선행 커밋 추가.

- [ ] **Step 2:** fixture 작성 — FE `generation-job-stage.ts:3`의 7개 키 기준:

```json
{
  "version": 1,
  "stages": ["queued", "planning", "image", "storage", "waiting", "completed", "failed"]
}
```

- [ ] **Step 3:** BE 계약 테스트:

```python
import json
from pathlib import Path

CONTRACT = json.loads(
    (Path(__file__).resolve().parents[2] / "apps" / "web" / "types" / "contracts" / "generation-stages.json").read_text()
)

def test_backend_stage_names_subset_of_contract():
    from orchestrator.app.generation_jobs.execution import KNOWN_PROGRESS_STAGES  # Step 1에서 확정한 심볼로 교체
    assert set(KNOWN_PROGRESS_STAGES) <= set(CONTRACT["stages"])
```

- [ ] **Step 4:** FE 계약 테스트:

```ts
import { describe, expect, it } from "vitest";
import contract from "../types/contracts/generation-stages.json";
import { generationStatusSteps } from "./generation-job-stage";
import type { GenerationStageKey } from "./generation-job-stage";

describe("generation stage contract", () => {
  it("FE stage keys equal the shared contract", () => {
    const feKeys: GenerationStageKey[] = ["queued", "planning", "image", "storage", "waiting", "completed", "failed"];
    expect([...feKeys].sort()).toEqual([...contract.stages].sort());
  });
});
```

- [ ] **Step 5:** 양쪽 실행:

```bash
cd /home/spai0722/codeit && uv run python -m pytest orchestrator/tests/test_generation_stage_contract.py -v
cd apps/web && npx vitest run lib/generation-job-stage.contract.test.ts
```
Expected: 둘 다 PASS. 이후 어느 쪽이 stage 이름을 바꾸면 해당 쪽 CI가 빨갛게 됨 — 무음 파손 차단.

- [ ] **Step 6: 커밋 (사용자)** — `git commit -m "test(contract): pin generation stage names across FE/BE"`

### Task 4.2: interrupt payload 계약 fixture

**Files:**
- Create: `apps/web/types/contracts/generation-job-interrupt.fixtures.json`
- Create: `orchestrator/tests/test_interrupt_contract.py` (BE가 실제 interrupt 예제를 생성해 fixture와 대조)
- Test: `apps/web/lib/generation-job-interrupt.contract.test.ts`

- [ ] **Step 1:** BE interrupt 생성 지점 확정:

```bash
grep -rn "interrupt" /home/spai0722/codeit/orchestrator/app/generation_jobs --include="*.py" | grep -iv test | head
```

- [ ] **Step 2:** 현재 BE가 만드는 interrupt 예제(질문형/컴플라이언스형 각 1개)를 fixture로 덤프 — BE 테스트에서 실제 빌더 함수를 호출해 생성 후 fixture와 `==` 비교 (fixture가 곧 스냅샷):

```python
def test_option_question_interrupt_matches_contract_fixture():
    interrupt = build_option_question_interrupt(...)  # Step 1에서 확정한 실제 빌더로 교체
    fixture = json.loads(FIXTURE_PATH.read_text())["optionQuestion"]
    assert interrupt == fixture
```

- [ ] **Step 3:** FE 테스트 — fixture를 `parseGenerationJobInterrupt`에 넣어 null 아님 + 타입 분기 정확성 검증:

```ts
import fixtures from "../types/contracts/generation-job-interrupt.fixtures.json";
import { parseGenerationJobInterrupt } from "./generation-job-interrupt";

it("parses the BE optionQuestion fixture", () => {
  const parsed = parseGenerationJobInterrupt(fixtures.optionQuestion);
  expect(parsed).not.toBeNull();
});
```

- [ ] **Step 4:** 양쪽 PASS 확인 후 커밋 (사용자) — `git commit -m "test(contract): pin interrupt payload shape across FE/BE"`

---

## Phase 5: BE 내구성 + 문서 (P7, P8, P10) — BE 팀 합의 필요, 별도 PR

⚠️ orchestrator app 코드 변경은 팀 코드 소유 영역 — 구현 전 담당자 합의. 합의 전이면 이 Phase는 `fix.md`-류 제안서로만 전달.

### Task 5.1: InMemorySaver → SqliteSaver (P8)

**Files:**
- Modify: `orchestrator/app/graph/builder.py` (두 그래프의 `checkpointer=InMemorySaver()`)
- Modify: `pyproject.toml` (`langgraph-checkpoint-sqlite` 의존성)
- Test: `orchestrator/tests/test_checkpointer_durability.py`

- [ ] **Step 1: 실패하는 테스트** — 그래프 재빌드(프로세스 재시작 시뮬레이션) 후 thread 체크포인트가 살아있는지:

```python
import tempfile
from pathlib import Path

def test_checkpoint_survives_graph_rebuild(tmp_path, monkeypatch):
    db_path = tmp_path / "checkpoints.sqlite"
    monkeypatch.setenv("LANGGRAPH_CHECKPOINT_DB", str(db_path))

    from orchestrator.app.graph.builder import build_intake_graph
    graph1 = build_intake_graph()
    config = {"configurable": {"thread_id": "t-durability"}}
    graph1.invoke({"user_input": "테스트 입력"}, config)  # 실제 초기 state 키는 create_initial_marketing_state 기준으로 교체

    graph2 = build_intake_graph()  # 재시작 시뮬레이션
    snapshot = graph2.get_state(config)
    assert snapshot.values  # InMemorySaver면 비어 있어 FAIL
```

- [ ] **Step 2:** 실행 — `uv run python -m pytest orchestrator/tests/test_checkpointer_durability.py -v` → FAIL
- [ ] **Step 3: 구현** (`builder.py`):

```python
import os
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

def _build_checkpointer():
    db_path = os.environ.get("LANGGRAPH_CHECKPOINT_DB", "")
    if not db_path:
        return InMemorySaver()  # 기존 동작 기본 유지 (opt-in)
    import sqlite3
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)
```
두 그래프의 `checkpointer=InMemorySaver()`를 `checkpointer=_build_checkpointer()`로 교체. `.env.example`에 `LANGGRAPH_CHECKPOINT_DB=` 항목 추가(기본 빈 값 = 기존 동작).

- [ ] **Step 4:** 전체 BE suite — `uv run python -m pytest orchestrator/tests && uv run python -m compileall orchestrator` → PASS
- [ ] **Step 5: 커밋 (사용자)** — `git commit -m "feat(graph): opt-in SqliteSaver checkpointer for HITL durability"`

### Task 5.2: BE prefix 통일 (P7) — 마이그레이션 안전 방식

- [ ] **Step 1:** `orchestrator/app/api/chat.py:14`의 `prefix="/v1/marketing/chat"`을 유지한 채, `app.py`에서 같은 라우터를 `/api/v1/marketing/chat`으로 **추가 마운트** (alias):

```python
    app.include_router(chat_router)  # 기존 경로 유지
    app.include_router(chat_router, prefix="/api")  # 신규 표준 경로
```
photo_router 동일.
- [ ] **Step 2:** Next 라우트(Task 1.3, 1.6)의 대상 경로를 `/api/v1/marketing/chat/*`로 전환.
- [ ] **Step 3:** 한 사이클 후 구 prefix 마운트 제거 (별도 PR).
- [ ] **Step 4: 커밋 (사용자)** — `git commit -m "feat(api): mount marketing chat router under standard /api/v1 prefix"`

### Task 5.3: 문서 갱신 (P10)

- [ ] **Step 1:** `apps/web/ROUTES.md`의 "mock 진행 화면"/"mock 광고 결과" 표기를 실제 동작 설명으로 갱신, BFF 단일화 후 아키텍처 1단락 추가.
- [ ] **Step 2:** `CLAUDE.md`(루트)에 BFF 단일화 사실 반영 (apps/bff deprecated, api 계층은 apps/web/app/api).
- [ ] **Step 3: 커밋 (사용자)** — `git commit -m "docs: update ROUTES.md and CLAUDE.md after BFF unification"`

---

## 실행 순서 / 분담 제안

| 순서 | Phase | 예상 규모 | 의존성 | 분담 가능 |
|---|---|---|---|---|
| 1 | Phase 0 + 1 (BFF 단일화) | 대 (~1세션) | 없음 | 단독 세션 권장 |
| 1' | Phase 2 (URL 빌더) | 소 (~30분) | 없음 | Phase 1과 다른 에이전트 병행 가능 |
| 2 | Phase 3 (컴포넌트 분해) | 대 (~1-2세션) | Phase 1 완료 | `ChatGenerateClient.tsx` 단독 점유 필수 |
| 3 | Phase 4 (계약 고정) | 중 | 없음 (독립) | 병행 가능 |
| 4 | Phase 5 (BE) | 중 | 팀 합의 | BE 담당자와 조율 |

## 리스크 / 롤백

- **Phase 1 롤백:** `NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000` 환경변수 하나로 즉시 Fastify 복귀 (Task 1.9 전까지 Fastify 코드 보존이 그 이유).
- **Phase 3 리스크 최대:** 매 Task 후 80개 회귀 테스트(특히 #5/#6 가드) green이 머지 조건. 한 Task라도 red면 다음 Task 진행 금지.
- **동시 편집:** 멀티 에이전트 환경(`ChatGenerateClient.tsx` 등) — 각 Task 시작 전 `git status`/`git pull`, 종료 전 전체 suite 재실행 (worktree 합의사항).
- **photo upload 디스크 의존:** Phase 1 헤더의 결정 (a)/(b) — 사용자 확인 전 Task 1.6은 (a)로 진행 가능하되 Vercel 배포 시 (b) 필수.

---
미커밋 정책: 모든 커밋은 사용자가 직접 수행. 이 문서는 계획서이며 코드 변경 없음.
근거 문서: `/home/spai0722/FE_BFF_BE_LOGIC_MAP.md` (P1~P10 정의).
