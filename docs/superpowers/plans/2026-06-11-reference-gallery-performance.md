# Reference Gallery Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the "찾기" reference gallery feel faster by showing cached template results immediately, reducing search request churn, and allowing reference images to be cached/optimized.

**Architecture:** Keep the UI behavior local to the existing `ReferenceBrowseStep` so the gallery can render stale cached results before the network returns. Preserve the current BFF/orchestrator image proxy path, but add cache headers for temporary reference assets. Use Next image optimization only for URLs we explicitly allow, leaving unknown external URLs unoptimized.

**Tech Stack:** Next.js 14, React 18, Vitest/Testing Library, Fastify BFF, FastAPI orchestrator, `next/image`.

---

## File Structure

- Modify `apps/web/components/generate/ReferenceBrowseStep.tsx`
  - Owns reference gallery query state, stale localStorage cache, debounce, and list rendering.
- Modify `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
  - Existing integration test home for reference gallery behavior.
- Modify `apps/bff/src/app.js`
  - Propagates or supplies `cache-control` on proxied binary reference assets.
- Modify `apps/bff/tests/generate.test.js`
  - Verifies temp reference asset proxy headers.
- Modify `orchestrator/app/api/routers/references.py`
  - Adds cache headers to temporary reference asset `FileResponse`.
- Modify `orchestrator/tests/test_api_references_router.py`
  - Verifies orchestrator temp reference asset cache headers.
- Create `apps/web/lib/image-optimization.ts`
  - Small URL helper that decides whether a URL can safely use Next image optimization.
- Create `apps/web/lib/image-optimization.test.ts`
  - Unit tests for the URL helper.
- Modify `apps/web/components/generate/AdCreativeCard.tsx`
  - Uses the image optimization helper for gallery cards.
- Modify `apps/web/components/generate/ReferenceStyleFlowStep.tsx`
  - Uses the same image optimization helper for reference detail/start images.
- Modify `apps/web/next.config.mjs`
  - Allows the configured BFF origin for Next image optimization.

---

### Task 1: Reference Gallery Stale Cache And Debounced Search

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
- Modify: `apps/web/components/generate/ReferenceBrowseStep.tsx`

- [ ] **Step 1: Write the failing stale-cache test**

Add this test near the existing reference gallery tests in `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`, after `"opens a selected reference template detail from the gallery"`:

```tsx
  it("shows cached reference templates immediately while refreshing the gallery", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listReferenceTemplates).mockClear();
    vi.mocked(api.listReferenceTemplates).mockReturnValueOnce(new Promise(() => undefined));
    window.localStorage.setItem(
      "easyads_reference_templates_cache_v1",
      JSON.stringify({
        entries: {
          "category=&keyword=&tags=&limit=30": {
            cachedAt: "2026-06-11T00:00:00.000Z",
            items: [
              {
                templateId: "cached_reference_1",
                title: "캐시된 샘플",
                description: "기다림 없이 먼저 보이는 샘플",
                category: "cafe",
                tags: ["캐시", "카페"],
                businessTypes: ["cafe"],
                adFormats: ["instagram_feed"],
                platforms: ["instagram"],
                aspectRatio: "1:1",
                thumbnailUrl: "http://127.0.0.1:4000/api/references/temp-assets/cache/ref.png",
                previewUrl: "http://127.0.0.1:4000/api/references/temp-assets/cache/ref.png",
                styleKeywords: ["quick"],
                colorPalette: ["#5AB4F2", "#FFFFFF"],
                layoutHint: "center_product",
                typographyHint: "bold_headline",
                popularityScore: 0.9,
                isSaved: false
              }
            ]
          }
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    expect(screen.getByText("캐시된 샘플")).toBeTruthy();
    expect(screen.queryByLabelText("샘플 목록 불러오는 중")).toBeNull();
    await waitFor(() =>
      expect(api.listReferenceTemplates).toHaveBeenCalledWith({
        keyword: "",
        category: "",
        tags: [],
        limit: 30
      })
    );
  });
```

- [ ] **Step 2: Run the stale-cache test to verify it fails**

Run:

```bash
npm --prefix apps/web run test -- app/generate/chat/ChatGenerateClient.test.tsx -t "shows cached reference templates"
```

Expected: FAIL because `"캐시된 샘플"` is not rendered and the loading skeleton remains while `listReferenceTemplates` is pending.

- [ ] **Step 3: Write the failing debounce test**

Add this test after the stale-cache test in `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`:

```tsx
  it("debounces reference gallery search requests", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listReferenceTemplates).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);
    await waitForReferenceTemplatesLoaded();
    vi.mocked(api.listReferenceTemplates).mockClear();

    vi.useFakeTimers();
    try {
      fireEvent.change(screen.getByLabelText("샘플 검색어"), { target: { value: "수" } });
      fireEvent.change(screen.getByLabelText("샘플 검색어"), { target: { value: "수박" } });

      expect(api.listReferenceTemplates).not.toHaveBeenCalled();

      await act(async () => {
        vi.advanceTimersByTime(299);
      });
      expect(api.listReferenceTemplates).not.toHaveBeenCalled();

      await act(async () => {
        vi.advanceTimersByTime(1);
      });

      await waitFor(() =>
        expect(api.listReferenceTemplates).toHaveBeenCalledWith({
          keyword: "수박",
          category: "",
          tags: ["수박"],
          limit: 30
        })
      );
    } finally {
      vi.useRealTimers();
    }
  });
```

- [ ] **Step 4: Run the debounce test to verify it fails**

Run:

```bash
npm --prefix apps/web run test -- app/generate/chat/ChatGenerateClient.test.tsx -t "debounces reference gallery search"
```

Expected: FAIL because the search request fires immediately on every input change and uses `limit: 60`.

- [ ] **Step 5: Implement cache helpers and debounce in `ReferenceBrowseStep.tsx`**

In `apps/web/components/generate/ReferenceBrowseStep.tsx`, update the imports:

```tsx
import { useEffect, useMemo, useState } from "react";
```

Keep the import unchanged; `useEffect`, `useMemo`, and `useState` are already present.

Add these constants and helpers below the `categories` constant:

```tsx
const REFERENCE_TEMPLATE_CACHE_STORAGE_KEY = "easyads_reference_templates_cache_v1";
const REFERENCE_TEMPLATE_CACHE_LIMIT = 30;
const REFERENCE_SEARCH_DEBOUNCE_MS = 300;

type ReferenceTemplateCacheEntry = {
  cachedAt: string;
  items: ReferenceTemplateCard[];
};

type ReferenceTemplateCachePayload = {
  entries?: Record<string, ReferenceTemplateCacheEntry>;
};

type ReferenceTemplateQuery = {
  keyword: string;
  category: string;
  tags: string[];
  limit: number;
};

function isCachedReferenceTemplate(value: unknown): value is ReferenceTemplateCard {
  if (!value || typeof value !== "object") {
    return false;
  }
  const template = value as { templateId?: unknown; title?: unknown };
  return typeof template.templateId === "string" && typeof template.title === "string";
}

function referenceTemplateCacheKey(query: ReferenceTemplateQuery): string {
  return [
    `category=${query.category}`,
    `keyword=${query.keyword}`,
    `tags=${query.tags.join(",")}`,
    `limit=${query.limit}`
  ].join("&");
}

function readReferenceTemplateCache(cacheKey: string): ReferenceTemplateCard[] {
  try {
    const raw = window.localStorage.getItem(REFERENCE_TEMPLATE_CACHE_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as ReferenceTemplateCachePayload;
    const entry = parsed.entries?.[cacheKey];
    return Array.isArray(entry?.items)
      ? entry.items.filter(isCachedReferenceTemplate).slice(0, REFERENCE_TEMPLATE_CACHE_LIMIT)
      : [];
  } catch {
    return [];
  }
}

function writeReferenceTemplateCache(cacheKey: string, items: ReferenceTemplateCard[]) {
  try {
    const raw = window.localStorage.getItem(REFERENCE_TEMPLATE_CACHE_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as ReferenceTemplateCachePayload) : {};
    const entries = parsed.entries ?? {};
    window.localStorage.setItem(
      REFERENCE_TEMPLATE_CACHE_STORAGE_KEY,
      JSON.stringify({
        entries: {
          ...entries,
          [cacheKey]: {
            cachedAt: new Date().toISOString(),
            items: items.slice(0, REFERENCE_TEMPLATE_CACHE_LIMIT)
          }
        }
      })
    );
  } catch {
    // The gallery can still render from memory when browser storage is unavailable.
  }
}

function useDebouncedValue(value: string, delayMs: number): string {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timerId = window.setTimeout(() => setDebouncedValue(value), delayMs);
    return () => window.clearTimeout(timerId);
  }, [delayMs, value]);

  return debouncedValue;
}
```

Replace the query state and effect block in `ReferenceBrowseStep` with this version:

```tsx
  const [templates, setTemplates] = useState<ReferenceTemplateCard[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const debouncedSearchTerm = useDebouncedValue(searchTerm, REFERENCE_SEARCH_DEBOUNCE_MS);
  const searchTags = useMemo(() => splitReferenceSearchTerms(debouncedSearchTerm), [debouncedSearchTerm]);
  const referenceQuery = useMemo<ReferenceTemplateQuery>(
    () => ({
      keyword: debouncedSearchTerm,
      category: selectedCategory,
      tags: searchTags,
      limit: REFERENCE_TEMPLATE_CACHE_LIMIT
    }),
    [debouncedSearchTerm, searchTags, selectedCategory]
  );
  const referenceQueryCacheKey = useMemo(() => referenceTemplateCacheKey(referenceQuery), [referenceQuery]);
  const visibleTemplates = useMemo(() => {
    const imageBackedTemplates = templates.filter(hasReferenceTemplateImage);
    const candidates = imageBackedTemplates.length > 0 ? imageBackedTemplates : templates;
    return [...candidates].sort((first, second) => second.popularityScore - first.popularityScore);
  }, [templates]);

  useEffect(() => {
    let cancelled = false;
    const cachedTemplates = readReferenceTemplateCache(referenceQueryCacheKey);
    if (cachedTemplates.length > 0) {
      setTemplates(cachedTemplates);
      setIsLoading(false);
    } else {
      setIsLoading(true);
    }
    setErrorMessage(null);

    listReferenceTemplates(referenceQuery)
      .then((response) => {
        if (cancelled) {
          return;
        }
        setTemplates(response.items);
        writeReferenceTemplateCache(referenceQueryCacheKey, response.items);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        if (cachedTemplates.length === 0) {
          setTemplates([]);
          setErrorMessage(error instanceof Error ? error.message : "샘플 목록을 불러오지 못했어요.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [referenceQuery, referenceQueryCacheKey, reloadToken]);
```

- [ ] **Step 6: Run the Task 1 tests to verify they pass**

Run:

```bash
npm --prefix apps/web run test -- app/generate/chat/ChatGenerateClient.test.tsx -t "shows cached reference templates|debounces reference gallery search|opens the reference gallery"
```

Expected: PASS. Existing React `act(...)` warnings from unrelated `StudioEntryStep` tests may appear only when the full file runs.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add apps/web/components/generate/ReferenceBrowseStep.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "perf(web): cache reference gallery results"
```

Expected: Commit succeeds with only the two listed files staged.

---

### Task 2: Cache Headers For Temporary Reference Assets

**Files:**
- Modify: `orchestrator/tests/test_api_references_router.py`
- Modify: `orchestrator/app/api/routers/references.py`
- Modify: `apps/bff/tests/generate.test.js`
- Modify: `apps/bff/src/app.js`

- [ ] **Step 1: Write the failing orchestrator cache-header assertion**

In `orchestrator/tests/test_api_references_router.py`, extend `test_temporary_reference_assets_are_exposed_without_local_paths` after the existing content assertion:

```python
    assert asset_response.headers["cache-control"] == "public, max-age=604800, immutable"
```

- [ ] **Step 2: Run the orchestrator test to verify it fails**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_api_references_router.py::test_temporary_reference_assets_are_exposed_without_local_paths -q
```

Expected: FAIL because the temporary reference asset response does not include the cache header.

- [ ] **Step 3: Implement orchestrator asset cache header**

In `orchestrator/app/api/routers/references.py`, replace the final line of `get_temporary_reference_asset`:

```python
    return FileResponse(asset_path)
```

with:

```python
    return FileResponse(
        asset_path,
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
```

- [ ] **Step 4: Run the orchestrator test to verify it passes**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_api_references_router.py::test_temporary_reference_assets_are_exposed_without_local_paths -q
```

Expected: PASS.

- [ ] **Step 5: Write the failing BFF cache-header assertion**

In `apps/bff/tests/generate.test.js`, modify the temp asset upstream response in `"proxies reference template list and temporary assets to the orchestrator"`:

```js
        return new Response(Buffer.from("image bytes"), {
          status: 200,
          headers: {
            "content-type": "image/png",
            "cache-control": "public, max-age=604800, immutable"
          }
        });
```

Then add this assertion after the existing `content-type` assertion:

```js
    expect(assetResponse.headers["cache-control"]).toBe("public, max-age=604800, immutable");
```

- [ ] **Step 6: Run the BFF reference proxy test to verify it fails**

Run:

```bash
npm --prefix apps/bff test -- generate.test.js -t "proxies reference template list"
```

Expected: FAIL because `proxyBinary` currently forwards `content-type` only.

- [ ] **Step 7: Implement BFF binary cache header propagation and fallback**

In `apps/bff/src/app.js`, replace `proxyBinary` with:

```js
async function proxyBinary({ fetchImpl, url, reply, cacheControl }) {
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
  const responseCacheControl = response.headers.get("cache-control") || cacheControl;
  if (responseCacheControl) {
    reply.header("cache-control", responseCacheControl);
  }
  return Buffer.from(await response.arrayBuffer());
}
```

Then update the temp-assets route call:

```js
  app.get("/api/references/temp-assets/:removalGroup/:filename", async (request, reply) =>
    proxyBinary({
      fetchImpl,
      url: `${orchestratorBaseUrl}/api/v1/references/temp-assets/${encodeURIComponent(request.params.removalGroup)}/${encodeURIComponent(request.params.filename)}`,
      reply,
      cacheControl: "public, max-age=604800, immutable"
    })
  );
```

- [ ] **Step 8: Run Task 2 tests to verify they pass**

Run:

```bash
npm --prefix apps/bff test -- generate.test.js -t "proxies reference template list"
PYTHONPATH=. uv run pytest orchestrator/tests/test_api_references_router.py::test_temporary_reference_assets_are_exposed_without_local_paths -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 2**

Run:

```bash
git add orchestrator/app/api/routers/references.py orchestrator/tests/test_api_references_router.py apps/bff/src/app.js apps/bff/tests/generate.test.js
git commit -m "perf(refs): cache temporary reference assets"
```

Expected: Commit succeeds with only the four listed files staged.

---

### Task 3: Enable Next Image Optimization For BFF Reference Images

**Files:**
- Create: `apps/web/lib/image-optimization.ts`
- Create: `apps/web/lib/image-optimization.test.ts`
- Modify: `apps/web/components/generate/AdCreativeCard.tsx`
- Modify: `apps/web/components/generate/ReferenceStyleFlowStep.tsx`
- Modify: `apps/web/next.config.mjs`

- [ ] **Step 1: Write the failing image optimization helper test**

Create `apps/web/lib/image-optimization.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";

describe("shouldUseNextImageOptimization", () => {
  it("enables optimization for local and configured BFF reference images", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_BFF_BASE_URL", "http://127.0.0.1:4000");
    const { shouldUseNextImageOptimization } = await import("./image-optimization");

    expect(shouldUseNextImageOptimization("/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png")).toBe(true);
    expect(shouldUseNextImageOptimization("http://127.0.0.1:4000/api/references/temp-assets/group/ref.png")).toBe(true);
    expect(shouldUseNextImageOptimization("https://cdn.example.com/reference.png")).toBe(false);
    expect(shouldUseNextImageOptimization("data:image/png;base64,abc")).toBe(false);
    expect(shouldUseNextImageOptimization(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Run the helper test to verify it fails**

Run:

```bash
npm --prefix apps/web run test -- lib/image-optimization.test.ts
```

Expected: FAIL because `apps/web/lib/image-optimization.ts` does not exist.

- [ ] **Step 3: Implement the image optimization helper**

Create `apps/web/lib/image-optimization.ts`:

```ts
const DEFAULT_BFF_BASE_URL = "http://127.0.0.1:4000";

function configuredBffOrigin(): string | null {
  try {
    return new URL(process.env.NEXT_PUBLIC_BFF_BASE_URL || DEFAULT_BFF_BASE_URL).origin;
  } catch {
    return null;
  }
}

export function shouldUseNextImageOptimization(src: string | null | undefined): boolean {
  if (!src || src.startsWith("data:") || src.startsWith("blob:")) {
    return false;
  }
  if (src.startsWith("/")) {
    return true;
  }
  try {
    return new URL(src).origin === configuredBffOrigin();
  } catch {
    return false;
  }
}
```

- [ ] **Step 4: Run the helper test to verify it passes**

Run:

```bash
npm --prefix apps/web run test -- lib/image-optimization.test.ts
```

Expected: PASS.

- [ ] **Step 5: Use the helper in gallery cards**

In `apps/web/components/generate/AdCreativeCard.tsx`, add this import:

```tsx
import { shouldUseNextImageOptimization } from "@/lib/image-optimization";
```

Replace:

```tsx
      unoptimized
```

with:

```tsx
      unoptimized={!shouldUseNextImageOptimization(creative.imageUrl)}
```

- [ ] **Step 6: Use the helper in reference detail/start images**

In `apps/web/components/generate/ReferenceStyleFlowStep.tsx`, add:

```tsx
import { shouldUseNextImageOptimization } from "@/lib/image-optimization";
```

Replace the selected style image:

```tsx
<Image alt="" className={styles.selectedStyleImage} fill sizes="112px" src={imageUrl} unoptimized />
```

with:

```tsx
<Image alt="" className={styles.selectedStyleImage} fill sizes="112px" src={imageUrl} unoptimized={!shouldUseNextImageOptimization(imageUrl)} />
```

Replace the detail hero image:

```tsx
<Image alt="" className={styles.referenceDetailImage} fill sizes="calc(100vw - 48px)" src={imageUrl} unoptimized />
```

with:

```tsx
<Image alt="" className={styles.referenceDetailImage} fill sizes="calc(100vw - 48px)" src={imageUrl} unoptimized={!shouldUseNextImageOptimization(imageUrl)} />
```

- [ ] **Step 7: Allow the BFF origin in Next image config**

Replace `apps/web/next.config.mjs` with:

```js
const DEFAULT_BFF_BASE_URL = "http://127.0.0.1:4000";

function bffRemotePattern() {
  try {
    const bffUrl = new URL(process.env.NEXT_PUBLIC_BFF_BASE_URL || DEFAULT_BFF_BASE_URL);
    return {
      protocol: bffUrl.protocol.replace(":", ""),
      hostname: bffUrl.hostname,
      port: bffUrl.port,
      pathname: "/api/references/**"
    };
  } catch {
    return null;
  }
}

const bffPattern = bffRemotePattern();

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: bffPattern ? [bffPattern] : []
  }
};

export default nextConfig;
```

- [ ] **Step 8: Run Task 3 web tests**

Run:

```bash
npm --prefix apps/web run test -- lib/image-optimization.test.ts app/generate/chat/ChatGenerateClient.test.tsx -t "shows realistic creative labels|opens a selected reference template detail"
npm --prefix apps/web run lint
```

Expected: PASS. Lint may keep existing warnings unrelated to these files.

- [ ] **Step 9: Commit Task 3**

Run:

```bash
git add apps/web/lib/image-optimization.ts apps/web/lib/image-optimization.test.ts apps/web/components/generate/AdCreativeCard.tsx apps/web/components/generate/ReferenceStyleFlowStep.tsx apps/web/next.config.mjs
git commit -m "perf(web): optimize reference image loading"
```

Expected: Commit succeeds with only the five listed files staged.

---

### Task 4: Verification Sweep

**Files:**
- No new files.

- [ ] **Step 1: Run focused web tests**

Run:

```bash
npm --prefix apps/web run test -- lib/image-optimization.test.ts app/api/generated-assets/route.test.ts lib/archive-creative.test.ts lib/api-client.test.ts app/generate/chat/ChatGenerateClient.test.tsx components/generate/OnboardingFlowStep.test.tsx components/generate/HomeEntryClient.test.tsx
```

Expected: PASS. Existing React `act(...)` warnings from `StudioEntryStep` are acceptable if test status is green.

- [ ] **Step 2: Run BFF tests**

Run:

```bash
npm --prefix apps/bff test -- generate.test.js
```

Expected: PASS.

- [ ] **Step 3: Run orchestrator reference tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_api_references_router.py -q
```

Expected: PASS.

- [ ] **Step 4: Run diff and lint checks**

Run:

```bash
git diff --check
npm --prefix apps/web run lint
```

Expected: `git diff --check` exits 0. Web lint exits 0; existing warnings can remain if they are unrelated to the touched files.

- [ ] **Step 5: Manual browser verification**

Start the services normally, then test these flows:

```bash
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000 npm --prefix apps/web run dev
```

Manual checks:
- Open `/reference`.
- The first visit can show skeletons while templates load.
- Navigate away and back to `/reference`; cached samples should appear immediately.
- Type `수`, then quickly `수박`; only the debounced final query should refresh the list.
- Open DevTools Network and reload `/reference`; `/api/references/temp-assets/...` responses should include `cache-control: public, max-age=604800, immutable`.
- BFF reference images from `http://127.0.0.1:4000/api/references/...` should route through Next image optimization requests when allowed by `next.config.mjs`.

- [ ] **Step 6: Final commit if verification changed no files**

Run:

```bash
git status --short
```

Expected: Only intended files are modified. If Task 1-3 commits were made, there should be no unstaged changes. If execution was done without intermediate commits, stage the final intended file set and commit:

```bash
git add apps/web/components/generate/ReferenceBrowseStep.tsx \
  apps/web/app/generate/chat/ChatGenerateClient.test.tsx \
  apps/bff/src/app.js apps/bff/tests/generate.test.js \
  orchestrator/app/api/routers/references.py orchestrator/tests/test_api_references_router.py \
  apps/web/lib/image-optimization.ts apps/web/lib/image-optimization.test.ts \
  apps/web/components/generate/AdCreativeCard.tsx \
  apps/web/components/generate/ReferenceStyleFlowStep.tsx \
  apps/web/next.config.mjs
git commit -m "perf: speed up reference gallery loading"
```

Expected: Commit succeeds and `git status --short` shows no intended reference-gallery performance changes left unstaged.

---

## Self-Review

- Spec coverage: The plan covers stale gallery list cache, debounced searching, temp asset cache headers through orchestrator and BFF, and selective Next image optimization for reference images.
- Red-flag scan: No unresolved filler language is used; each code-changing step includes concrete code.
- Type consistency: The cache key, localStorage key, query shape, and helper names are consistent across tests and implementation snippets.
