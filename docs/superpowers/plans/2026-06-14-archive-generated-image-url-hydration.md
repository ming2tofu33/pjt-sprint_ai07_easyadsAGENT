# Archive Generated Image URL Hydration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make real GPT-image generation results render in archive list/detail cards instead of falling back to placeholder/mock visuals when archive row URL columns are empty.

**Architecture:** Keep generated assets as the source of truth in `generation_outputs.result_payload`, because signed R2 URLs should not be copied permanently into `archive_items.image_url`. Archive list queries must hydrate the same `output_result_payload` that archive detail already uses, and frontend session snapshots must prefer public result URLs when the backend returns them. This keeps the fix narrow: repository selection, archive response mapping coverage, and local browser creative mapping.

**Tech Stack:** FastAPI/Pydantic service layer, psycopg repository SQL, pytest, Next.js/React, TypeScript, Vitest.

---

## File Structure

- Modify `orchestrator/app/db/repositories/archive_items.py`
  - Responsibility: SQL selection for archive list/detail rows.
  - Change: include `o.result_payload as output_result_payload` in `_SELECT_ARCHIVE_LIST`, matching `_SELECT_ARCHIVE_WITH_OUTPUT`.

- Modify `orchestrator/tests/test_archive.py`
  - Responsibility: repository/service regression coverage for archive SQL and archive list response hydration.
  - Change: replace the old "list query omits output payload" expectation with "list query includes output payload".

- Modify `orchestrator/tests/test_url_policy.py`
  - Responsibility: URL sanitization and archive row-to-response behavior.
  - Change: add a test proving `archive_item_from_row()` uses `output_result_payload.final_image_url`/`download_url` when archive item URL columns and asset public URLs are empty.

- Modify `apps/web/types/marketing.ts`
  - Responsibility: shared chat brief shape.
  - Change: add optional `finalImageUrl` and `downloadUrl`.

- Modify `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Responsibility: convert completed generation jobs into chat brief snapshots.
  - Change: copy `final_image_url` and `download_url` from `result_payload` into `ChatBrief`.

- Modify `apps/web/lib/generated-creative-storage.ts`
  - Responsibility: turn completed chat snapshots into local recent creative cards.
  - Change: prefer `brief.finalImageUrl`, then `brief.downloadUrl`, then local generated asset URL built from `brief.finalImagePath`.

- Modify `apps/web/lib/generated-creative-storage.test.ts`
  - Responsibility: local recent creative snapshot regression coverage.
  - Change: add a test proving public result URLs are stored and used before local `/api/generated-assets` paths.

- Modify `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
  - Responsibility: completed job-to-chat response conversion coverage.
  - Change: add a test proving completed job `result_payload.final_image_url/download_url` are preserved on the normalized brief.

---

### Task 1: Hydrate Archive List Rows From Generation Output Payload

**Files:**
- Modify: `orchestrator/app/db/repositories/archive_items.py`
- Test: `orchestrator/tests/test_archive.py`
- Test: `orchestrator/tests/test_url_policy.py`

- [ ] **Step 1: Write the failing repository SQL test**

Replace `test_archive_list_query_omits_output_payload_by_default` in `orchestrator/tests/test_archive.py` with:

```python
def test_archive_list_query_includes_output_payload_for_url_hydration(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    repo.list_archive_item_rows(workspace_id="workspace_uuid", limit=20, offset=0, connection=conn)

    sql = conn.cursor_obj.calls[0][0]
    assert "o.result_payload as output_result_payload" in sql
```

- [ ] **Step 2: Write the failing archive response hydration test**

Add this test after `test_archive_item_from_row_keeps_https_url` in `orchestrator/tests/test_url_policy.py`:

```python
def test_archive_item_from_row_uses_output_payload_url_when_archive_urls_are_empty():
    """목록 row의 archive URL 컬럼이 비어도 output result payload의 R2 URL을 사용한다."""
    from orchestrator.app.archive.service import archive_item_from_row

    row = {
        "public_archive_id": "archive_generated",
        "title": "Generated",
        "asset_public_url": None,
        "thumbnail_public_url": None,
        "image_url": None,
        "thumbnail_url": None,
        "output_result_payload": {
            "final_image_url": "https://r2.example.com/generated/final.png",
            "download_url": "https://r2.example.com/generated/download.png",
        },
    }

    result = archive_item_from_row(row)

    assert result.image_url == "https://r2.example.com/generated/download.png"
    assert result.download_url == "https://r2.example.com/generated/download.png"
```

- [ ] **Step 3: Run backend tests and verify failure**

Run:

```bash
PYTHONPATH=$PWD uv run pytest orchestrator/tests/test_archive.py::test_archive_list_query_includes_output_payload_for_url_hydration orchestrator/tests/test_url_policy.py::test_archive_item_from_row_uses_output_payload_url_when_archive_urls_are_empty -q
```

Expected before implementation:

```text
FAILED orchestrator/tests/test_archive.py::test_archive_list_query_includes_output_payload_for_url_hydration
```

The URL hydration test may already pass for detail-style rows; the repository SQL test must fail because list rows currently omit `output_result_payload`.

- [ ] **Step 4: Implement minimal SQL fix**

In `orchestrator/app/db/repositories/archive_items.py`, update `_SELECT_ARCHIVE_LIST` to match detail hydration:

```python
_SELECT_ARCHIVE_LIST = """
select
    i.*,
    j.public_job_id as j_public_job_id,
    o.public_output_id,
    o.result_payload as output_result_payload,
    o.is_final,
    t.public_thread_id,
    a.public_url as asset_public_url,
    a.storage_provider,
    a.mime_type as asset_mime_type,
    a.width as asset_width,
    a.height as asset_height,
    ta.public_url as thumbnail_public_url
from archive_items i
left join generation_jobs j on j.id = i.job_id
left join generation_outputs o on o.id = i.output_id
left join chat_threads t on t.id = o.thread_id
left join assets a on a.id = i.asset_id
left join assets ta on ta.id = o.thumbnail_asset_id
"""
```

- [ ] **Step 5: Run backend tests and verify pass**

Run:

```bash
PYTHONPATH=$PWD uv run pytest orchestrator/tests/test_archive.py::test_archive_list_query_includes_output_payload_for_url_hydration orchestrator/tests/test_url_policy.py::test_archive_item_from_row_uses_output_payload_url_when_archive_urls_are_empty -q
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit backend slice**

```bash
git add orchestrator/app/db/repositories/archive_items.py orchestrator/tests/test_archive.py orchestrator/tests/test_url_policy.py
git commit -m "fix(orchestrator): hydrate archive list result urls"
```

---

### Task 2: Preserve Public Result URLs In Frontend Generated Creative Snapshots

**Files:**
- Modify: `apps/web/types/marketing.ts`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/lib/generated-creative-storage.ts`
- Test: `apps/web/lib/generated-creative-storage.test.ts`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Write failing local snapshot test**

Add this test after `stores generated chat results as archive creatives` in `apps/web/lib/generated-creative-storage.test.ts`:

```typescript
  it("prefers public result URLs over local generated asset paths", () => {
    const creatives = addGeneratedCreativeSnapshot({
      prompt: "한우 고기 광고 만들어줘",
      jobId: "job_r2",
      threadId: "thread_r2",
      context: {
        businessType: "음식점",
        itemOrService: "한우 고기",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [{ id: "copy_1", headline: "최고다 한우고기" }],
      selectedCopyId: "copy_1",
      selectedChannelId: "instagram-feed",
      selectedTone: "감성적인",
      customDirection: "",
      brief: {
        purpose: "신메뉴 출시",
        item: "한우 고기",
        copy: "최고다 한우고기",
        tone: "감성적인 분위기",
        channel: "인스타 피드 (1:1)",
        imageDirection: "한우 고기 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
        finalImagePath: "data/outputs/job_r2/final_composite.png",
        finalImageUrl: "https://r2.example.com/generated/final.png",
        downloadUrl: "https://r2.example.com/generated/download.png"
      }
    });

    expect(creatives).toHaveLength(1);
    expect(creatives[0].imageUrl).toBe("https://r2.example.com/generated/final.png");
  });
```

- [ ] **Step 2: Write failing completed job conversion test**

Add this test after `rejects completed generation jobs when the final brief is empty` in `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`:

```typescript
  it("preserves public result URLs when converting completed generation jobs", async () => {
    const chatClientModule = (await import("./ChatGenerateClient")) as typeof import("./ChatGenerateClient") & {
      generationJobToChatTurnResponse: (job: unknown, copyGenerationMode?: "suggest_candidates") => {
        type: "brief_ready";
        brief: {
          finalImagePath?: string | null;
          finalImageUrl?: string | null;
          downloadUrl?: string | null;
        };
      };
    };

    const response = chatClientModule.generationJobToChatTurnResponse({
      job_id: "job_with_r2_url",
      thread_id: "thread_with_r2_url",
      status: "done",
      progress: { progress_percent: 100, current_stage: "completed" },
      result_payload: {
        final_image_path: "data/outputs/job_with_r2_url/final.png",
        final_image_url: "https://r2.example.com/generated/final.png",
        download_url: "https://r2.example.com/generated/download.png",
        final_brief: {
          promotion_goal: "신메뉴 출시",
          item_or_service: "한우 고기",
          headline: "최고다 한우고기",
          brand_tone: "감성적인",
          selected_channel_id: "인스타 피드 (1:1)",
          visual_direction: "한우 고기 중심의 깔끔한 광고 배경과 문구 여백을 구성해요."
        }
      },
      metadata: {},
      created_at: "2026-06-14T00:00:00.000Z",
      updated_at: "2026-06-14T00:00:00.000Z"
    });

    expect(response.brief.finalImagePath).toBe("data/outputs/job_with_r2_url/final.png");
    expect(response.brief.finalImageUrl).toBe("https://r2.example.com/generated/final.png");
    expect(response.brief.downloadUrl).toBe("https://r2.example.com/generated/download.png");
  });
```

- [ ] **Step 3: Run frontend tests and verify failure**

Run:

```bash
npm --prefix apps/web test -- generated-creative-storage.test.ts ChatGenerateClient.test.tsx --run
```

Expected before implementation:

```text
FAIL apps/web/lib/generated-creative-storage.test.ts
FAIL apps/web/app/generate/chat/ChatGenerateClient.test.tsx
```

The first test fails because `creativeFromSnapshot()` ignores `finalImageUrl`. The second fails because `normalizeChatBrief()` does not populate `finalImageUrl` or `downloadUrl`.

- [ ] **Step 4: Add public URL fields to ChatBrief**

In `apps/web/types/marketing.ts`, update `ChatBrief`:

```typescript
export type ChatBrief = {
  purpose: string;
  item: string;
  copy: string;
  tone: string;
  channel: string;
  imageDirection: string;
  finalImagePath?: string | null;
  finalImageUrl?: string | null;
  downloadUrl?: string | null;
};
```

- [ ] **Step 5: Preserve result URLs during completed job conversion**

In `apps/web/app/generate/chat/ChatGenerateClient.tsx`, update `normalizeChatBrief()`:

```typescript
  const finalImagePath = getPayloadString(brief, "finalImagePath", "final_image_path") ?? getPayloadString(payload, "finalImagePath", "final_image_path");
  const finalImageUrl = getPayloadString(brief, "finalImageUrl", "final_image_url") ?? getPayloadString(payload, "finalImageUrl", "final_image_url");
  const downloadUrl = getPayloadString(brief, "downloadUrl", "download_url") ?? getPayloadString(payload, "downloadUrl", "download_url");

  return {
    purpose: getPayloadString(brief, "purpose", "promotion_goal") ?? context.promotionGoal,
    item: getPayloadString(brief, "item", "item_or_service") ?? context.itemOrService,
    copy,
    tone: getPayloadString(brief, "tone", "brand_tone", "selected_tone") ?? "",
    channel: getPayloadString(brief, "channel", "selected_channel_id", "requested_ad_format") ?? "",
    imageDirection,
    finalImagePath,
    finalImageUrl,
    downloadUrl
  };
```

- [ ] **Step 6: Prefer public URLs in local creative cards**

In `apps/web/lib/generated-creative-storage.ts`, update `creativeFromSnapshot()` and `addGeneratedCreativeSnapshot()`:

```typescript
function resolveSnapshotImageUrl(snapshot: GeneratedCreativeSnapshot): string | null {
  return snapshot.brief.finalImageUrl || snapshot.brief.downloadUrl || buildGeneratedAssetUrl(snapshot.brief.finalImagePath);
}

function creativeFromSnapshot(snapshot: GeneratedCreativeSnapshot): MockCreative {
  const channelMatch = snapshot.brief.channel.match(/\(([^)]+)\)/);
  const imageUrl = resolveSnapshotImageUrl(snapshot);
  return {
    id: `generated-${snapshot.jobId}`,
    title: snapshot.brief.copy,
    subtitle: `${snapshot.brief.item} · ${snapshot.brief.channel}`,
    format: channelMatch?.[1] ?? snapshot.brief.channel,
    imageUrl,
    date: "방금 생성",
    tone: "strawberry",
    badge: "실제 생성",
    status: "saved",
    channel: snapshot.brief.channel.replace(/\s*\(.+\)/, ""),
    fileName: "final_composite.png",
    fileType: "PNG",
    storage: "브라우저 임시 보관함",
    savedAt: "방금 생성",
    tags: [
      snapshot.context.businessType,
      snapshot.context.itemOrService,
      snapshot.context.promotionGoal,
      snapshot.brief.channel.replace(/\s*\(.+\)/, "")
    ].filter(Boolean)
  };
}

export function addGeneratedCreativeSnapshot(snapshot: GeneratedCreativeSnapshot): MockCreative[] {
  if (!resolveSnapshotImageUrl(snapshot)) {
    return readGeneratedCreatives();
  }
  const creative = creativeFromSnapshot(snapshot);
  const existing = readGeneratedCreatives().filter((item) => item.id !== creative.id);
  const nextCreatives = [creative, ...existing].slice(0, 5);
  try {
    window.localStorage.setItem(GENERATED_CREATIVES_STORAGE_KEY, JSON.stringify(nextCreatives));
  } catch {
    // The generated result still stays available through the active chat snapshot.
  }
  return nextCreatives;
}
```

- [ ] **Step 7: Run frontend tests and verify pass**

Run:

```bash
npm --prefix apps/web test -- generated-creative-storage.test.ts ChatGenerateClient.test.tsx --run
```

Expected:

```text
PASS apps/web/lib/generated-creative-storage.test.ts
PASS apps/web/app/generate/chat/ChatGenerateClient.test.tsx
```

- [ ] **Step 8: Commit frontend slice**

```bash
git add apps/web/types/marketing.ts apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/lib/generated-creative-storage.ts apps/web/lib/generated-creative-storage.test.ts apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "fix(web): preserve generated image urls in recent ads"
```

---

### Task 3: End-To-End Verification

**Files:**
- No additional source files.

- [ ] **Step 1: Run focused backend archive tests**

Run:

```bash
PYTHONPATH=$PWD uv run pytest orchestrator/tests/test_archive.py orchestrator/tests/test_url_policy.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run focused frontend tests**

Run:

```bash
npm --prefix apps/web test -- generated-creative-storage.test.ts archive-creative.test.ts ChatGenerateClient.test.tsx --run
```

Expected:

```text
PASS
```

- [ ] **Step 3: Inspect changed files**

Run:

```bash
git diff --stat
git diff -- orchestrator/app/db/repositories/archive_items.py orchestrator/tests/test_archive.py orchestrator/tests/test_url_policy.py apps/web/types/marketing.ts apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/lib/generated-creative-storage.ts apps/web/lib/generated-creative-storage.test.ts apps/web/app/generate/chat/ChatGenerateClient.test.tsx
```

Expected:

```text
Only archive URL hydration and generated creative URL preservation changes are present.
```

- [ ] **Step 4: Optional production data sanity check**

Run this only when connected to the production database from a safe shell:

```bash
uv run python - <<'PY'
from orchestrator.app.archive.service import list_archive_items

items, _ = list_archive_items(
    user_id="06e72932-f0bd-4923-8b40-b4526291e500",
    account_type="user",
    limit=1,
    include_total=False,
)
item = items[0]
print({
    "ad_id": item.ad_id,
    "image_url_present": bool(item.image_url),
    "download_url_present": bool(item.download_url),
})
PY
```

Expected:

```text
{'ad_id': 'archive_...', 'image_url_present': True, 'download_url_present': True}
```

- [ ] **Step 5: Commit verification note if docs were changed**

```bash
git status --short
```

Expected:

```text
No unexpected source changes besides the implementation and this plan document.
```

---

## Self-Review

**Spec coverage:** The plan covers the observed production symptom: actual GPT-image results existed in `generation_outputs.result_payload`, but archive list/local cards lost the image URL and rendered placeholder visuals.

**Placeholder scan:** No `TBD`, `TODO`, or deferred implementation language remains. Code snippets include exact function names, fields, files, and commands.

**Type consistency:** `ChatBrief.finalImageUrl` and `ChatBrief.downloadUrl` are introduced in the shared type, populated by `normalizeChatBrief()`, and consumed by `generated-creative-storage.ts`.
