# UI LangGraph Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** UI에서 선택하거나 업로드한 입력값이 BFF와 Orchestrator를 거쳐 LangGraph 최종 생성 체인까지 보존되는지 하나씩 검증하고, 누락된 연결을 구현한다. 특히 photo image-to-image, 직접 reference-image, 문구 선택/직접 입력 interrupt, validation feedback, UI-graph coverage를 실제 동작 기준으로 맞춘다.

**Architecture:** 백엔드 생성 알고리즘은 새로 만들지 않고, 이미 존재하는 LangGraph state 필드와 노드(`source_image_path`, `reference_image_path`, `selected_reference_template_id`, copy interrupt, validation summary)를 UI/BFF/API payload와 연결한다. 각 기능은 먼저 실패하는 테스트를 만들고, 그 테스트가 통과하도록 최소 범위로 구현한다.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest, Testing Library, BFF Node/Express, FastAPI/Pydantic, LangGraph, pytest

---

## Current Diagnosis

현재 백엔드에는 그래프 노드와 state 필드가 이미 꽤 많이 준비되어 있다. 문제는 UI가 일부 값을 화면 안에서만 쓰거나 metadata에만 넣고, 최종 `generation-jobs` 그래프 실행 state로 넘기지 못하는 지점이 있다는 점이다.

핵심 누락은 다음과 같다.

| Gap | 현재 상태 | 목표 상태 |
| --- | --- | --- |
| Photo image-to-image | `/marketing/photo/start`에는 `sourceImagePath`가 전달되지만 최종 `createGenerationJob()` payload에는 빠질 수 있음 | 최종 generation job state에 `source_image_path`가 들어가고 `t2i_request_builder`의 input image로 사용됨 |
| Direct reference image | reference template ID는 연결되어 있으나 사용자가 직접 올린 reference image 경로는 최종 그래프로 이어지는 UI가 부족함 | `referenceImagePath`가 graph state에 저장되고 `reference_preprocess` 경로를 탈 수 있음 |
| Copy/channel/tone/custom text | UI 선택값 일부가 metadata에만 들어가 있음 | root payload와 graph state에 first-class 값으로 보존됨 |
| Graph interrupt UI | `option_question` 계열은 UI가 다루지만 `copy_candidate_selection`, `custom_copy_input`은 최종 그래프 resume UI가 부족함 | interrupt type별 UI와 resume payload를 제공함 |
| Validation feedback | graph 결과의 `validation_summary`가 화면에 충분히 노출되지 않음 | 생성 결과 화면에서 검수 결과를 유저 친화적인 문구로 보여줌 |
| Coverage matrix | 일부 항목이 실제 연결보다 낙관적으로 표시될 수 있음 | 테스트가 실제 payload/state 연결을 기준으로 coverage를 판정함 |

---

## File Structure

### Frontend

```text
apps/web/app/generate/chat/ChatGenerateClient.tsx
apps/web/app/generate/chat/ChatGenerateClient.test.tsx
apps/web/app/api/generation-jobs/route.ts
apps/web/components/generate/ChatStartStep.tsx
apps/web/components/generate/GenerationCompleteStep.tsx
apps/web/components/generate/GenerationJobInterruptStep.tsx
apps/web/components/generate/ValidationSummaryPanel.tsx
apps/web/lib/api-client.ts
apps/web/lib/api-client.test.ts
apps/web/lib/generation-job-interrupt.ts
apps/web/lib/generation-job-interrupt.test.ts
apps/web/lib/generation-request-context.ts
apps/web/lib/generation-request-context.test.ts
apps/web/lib/ui-graph-coverage.ts
apps/web/lib/ui-graph-coverage.test.ts
apps/web/lib/ui-orchestrator-route-coverage.ts
apps/web/lib/ui-orchestrator-route-coverage.test.ts
apps/web/types/marketing.ts
```

### BFF

```text
apps/bff/src/app.js
apps/bff/tests/generate.test.js
```

### Orchestrator

```text
orchestrator/app/api/schemas/generation_jobs.py
orchestrator/app/generation_jobs/service.py
orchestrator/app/generation_jobs/execution.py
orchestrator/tests/test_generation_jobs_api.py
orchestrator/tests/test_generation_job_graph_execution.py
orchestrator/tests/test_ui_graph_coverage_contract.py
```

---

## Implementation Steps

### Step 0. Branch And Worktree Safety Check

- [x] Confirm current branch is `feat/fe/generation-engine-selector`.
- [x] Confirm the working tree has existing dirty files from team/user work.
- [x] Do not revert or restage unrelated dirty files.
- [x] Before editing, list target files for the current step and only touch those files.

Commands:

```bash
git branch --show-current
git status --short
```

Expected result:

- Branch is not `develop` or `main`.
- Existing dirty files are acknowledged.
- Each later commit stages only the files touched for that logical change.

---

### Step 1. Make The Coverage Matrix Honest First

Purpose: implementation should be driven by an explicit map of backend graph capabilities versus UI coverage.

- [x] Add or update coverage rows for these graph capabilities:
  - `photo.final-source-image`
  - `reference.direct-image-upload`
  - `generation.copy-candidate-selection-interrupt`
  - `generation.custom-copy-input-interrupt`
  - `generation.selected-copy-state`
  - `generation.selected-channel-state`
  - `generation.selected-tone-state`
  - `validation.feedback-visible`
- [x] Mark only already-proven flows as connected.
- [x] Keep missing flows as `disconnected` until their tests pass.
- [x] Add tests that fail if a capability is marked connected without a linked UI route, API payload, and graph state field.

Files:

```text
apps/web/lib/ui-graph-coverage.ts
apps/web/lib/ui-graph-coverage.test.ts
apps/web/lib/ui-orchestrator-route-coverage.ts
apps/web/lib/ui-orchestrator-route-coverage.test.ts
```

Failing test to add:

```ts
it("does not mark direct reference image upload connected until UI, API, and graph state are all mapped", () => {
  const row = getUiOrchestratorRouteCoverage().find(
    (item) => item.id === "reference.direct-image-upload",
  );

  expect(row).toMatchObject({
    status: "disconnected",
    graphStateField: "reference_image_path",
  });
});
```

Commands:

```bash
cd apps/web
npm test -- --run lib/ui-graph-coverage.test.ts lib/ui-orchestrator-route-coverage.test.ts
```

Expected result:

- Tests pass with honest disconnected rows.
- Coverage percentage may decrease temporarily. That is acceptable because it reflects the real integration state.

Commit:

```bash
git add apps/web/lib/ui-graph-coverage.ts apps/web/lib/ui-graph-coverage.test.ts apps/web/lib/ui-orchestrator-route-coverage.ts apps/web/lib/ui-orchestrator-route-coverage.test.ts
git commit -m "test(generation): expose ui graph coverage gaps"
```

---

### Step 2. Preserve Photo Source Image Into Final Graph Job

Purpose: when a user starts from an uploaded photo, the final generation job must receive the same uploaded image path.

- [x] Add `sourceImagePath` to `ChatFlowState` or the equivalent persisted snapshot type.
- [x] Store `sourceImagePath` after photo upload succeeds.
- [x] Include `sourceImagePath` in `createGenerationJob()` payload.
- [x] Normalize `sourceImagePath` to `source_image_path` in the Next route if needed.
- [x] Add orchestrator state restoration support so `source_image_path` survives into graph execution.
- [x] Verify `t2i_request_builder` can see `state["source_image_path"]`.

Frontend failing test:

```ts
it("passes uploaded photo sourceImagePath to the final generation job", async () => {
  mockUploadPhotoAsset.mockResolvedValue({
    sourceImagePath: "uploads/source/menu-photo.png",
    filename: "menu-photo.png",
  });

  render(<ChatGenerateClient />);

  await user.upload(screen.getByLabelText("사진 업로드"), imageFile);
  await user.click(screen.getByRole("button", { name: "생성 결과 확인하기" }));

  expect(mockCreateGenerationJob).toHaveBeenCalledWith(
    expect.objectContaining({
      sourceImagePath: "uploads/source/menu-photo.png",
    }),
  );
});
```

Orchestrator failing test:

```python
def test_generation_job_preserves_source_image_path_in_state():
    request = GenerationJobCreateRequest(
        userInput="딸기라떼 사진으로 광고 만들어줘",
        sourceImagePath="uploads/source/strawberry-latte.png",
    )

    snapshot = build_generation_job_input_snapshot(request)

    assert snapshot.state_payload["source_image_path"] == "uploads/source/strawberry-latte.png"
```

Files:

```text
apps/web/app/generate/chat/ChatGenerateClient.tsx
apps/web/app/generate/chat/ChatGenerateClient.test.tsx
apps/web/app/api/generation-jobs/route.ts
apps/web/types/marketing.ts
orchestrator/app/api/schemas/generation_jobs.py
orchestrator/app/generation_jobs/service.py
orchestrator/tests/test_generation_jobs_api.py
orchestrator/tests/test_generation_job_graph_execution.py
```

Commands:

```bash
cd apps/web
npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx

cd ../..
uv run python -m pytest orchestrator/tests/test_generation_jobs_api.py orchestrator/tests/test_generation_job_graph_execution.py
```

Expected result:

- Final generation job payload contains `sourceImagePath`.
- Orchestrator snapshot contains `source_image_path`.
- Existing graph can route through product/image input processing without adding a new algorithm.

Commit:

```bash
git add apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx apps/web/app/api/generation-jobs/route.ts apps/web/types/marketing.ts orchestrator/app/api/schemas/generation_jobs.py orchestrator/app/generation_jobs/service.py orchestrator/tests/test_generation_jobs_api.py orchestrator/tests/test_generation_job_graph_execution.py
git commit -m "feat(generation): preserve photo source image for graph jobs"
```

---

### Step 3. Connect Direct Reference Image Upload

Purpose: reference template selection is not the same as direct reference image upload. Users should be able to attach a reference image and have that image path reach `reference_preprocess`.

- [x] Add UI state for `referenceImageFile` and `referenceImagePath`.
- [x] Add a reference-image attach control in the generation entry flow where it belongs visually.
- [x] Reuse the existing asset upload API if it can store a generic image path, otherwise add a typed upload route that returns `referenceImagePath`.
- [x] Persist `referenceImagePath` in generation request context when navigating across steps.
- [x] Include `referenceImagePath` in `startChatGeneration()`, `startPhotoGeneration()`, and final `createGenerationJob()` payload where relevant.
- [x] Normalize `referenceImagePath` to `reference_image_path` in route/BFF/orchestrator payloads.
- [x] Restore `reference_image_path` into graph state.

Frontend failing test:

```ts
it("passes uploaded referenceImagePath to the final generation job", async () => {
  mockUploadReferenceAsset.mockResolvedValue({
    referenceImagePath: "uploads/reference/clean-layout.png",
    filename: "clean-layout.png",
  });

  render(<ChatGenerateClient />);

  await user.upload(screen.getByLabelText("레퍼런스 이미지 첨부"), referenceFile);
  await user.type(screen.getByPlaceholderText("광고 방향을 입력해주세요"), "이 분위기로 카페 광고");
  await user.click(screen.getByRole("button", { name: "전송" }));
  await user.click(screen.getByRole("button", { name: "생성 결과 확인하기" }));

  expect(mockCreateGenerationJob).toHaveBeenCalledWith(
    expect.objectContaining({
      referenceImagePath: "uploads/reference/clean-layout.png",
    }),
  );
});
```

Orchestrator failing test:

```python
def test_generation_job_preserves_reference_image_path_in_state():
    request = GenerationJobCreateRequest(
        userInput="이 레퍼런스 느낌으로 포스터 만들어줘",
        referenceImagePath="uploads/reference/poster-layout.png",
    )

    snapshot = build_generation_job_input_snapshot(request)

    assert snapshot.state_payload["reference_image_path"] == "uploads/reference/poster-layout.png"
```

Files:

```text
apps/web/components/generate/ChatStartStep.tsx
apps/web/app/generate/chat/ChatGenerateClient.tsx
apps/web/app/generate/chat/ChatGenerateClient.test.tsx
apps/web/lib/api-client.ts
apps/web/lib/api-client.test.ts
apps/web/lib/generation-request-context.ts
apps/web/lib/generation-request-context.test.ts
apps/web/types/marketing.ts
apps/bff/src/app.js
apps/bff/tests/generate.test.js
orchestrator/app/api/schemas/generation_jobs.py
orchestrator/app/generation_jobs/service.py
orchestrator/tests/test_generation_jobs_api.py
orchestrator/tests/test_generation_job_graph_execution.py
```

Commands:

```bash
cd apps/web
npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx lib/api-client.test.ts lib/generation-request-context.test.ts

cd ../bff
npm test -- tests/generate.test.js

cd ../..
uv run python -m pytest orchestrator/tests/test_generation_jobs_api.py orchestrator/tests/test_generation_job_graph_execution.py
```

Expected result:

- Direct reference image path reaches graph state as `reference_image_path`.
- Coverage row `reference.direct-image-upload` can move to connected after test proof.

Commit:

```bash
git add apps/web/components/generate/ChatStartStep.tsx apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx apps/web/lib/api-client.ts apps/web/lib/api-client.test.ts apps/web/lib/generation-request-context.ts apps/web/lib/generation-request-context.test.ts apps/web/types/marketing.ts apps/bff/src/app.js apps/bff/tests/generate.test.js orchestrator/app/api/schemas/generation_jobs.py orchestrator/app/generation_jobs/service.py orchestrator/tests/test_generation_jobs_api.py orchestrator/tests/test_generation_job_graph_execution.py
git commit -m "feat(generation): connect direct reference image input"
```

---

### Step 4. Promote Selected UI Values From Metadata To Graph State

Purpose: selected copy, selected channel, selected tone, and directly typed copy should not be metadata-only if graph nodes need them.

- [x] Add typed fields to the generation job request:
  - `selectedCopyId`
  - `selectedChannelId`
  - `selectedTone`
  - `customDirection`
  - `userCustomHeadline`
  - `userCustomSubcopy`
- [x] Normalize camelCase to snake_case in the Next route and BFF.
- [x] Add Pydantic aliases in `GenerationJobCreateRequest`.
- [x] Include these fields in generation job state snapshot.
- [x] Keep metadata copies only for analytics/debugging if useful.
- [x] Update UI tests so selected values are expected at root payload level.

Frontend failing test:

```ts
it("sends selected copy, channel, tone, and custom copy as graph fields", async () => {
  render(<ChatGenerateClient />);

  await selectCopyCandidate("copy_2");
  await selectChannel("instagram_story");
  await selectTone("감성적인");
  await typeCustomCopy({
    headline: "오늘만 만나는 딸기라떼",
    subcopy: "신선한 딸기의 달콤함을 담았어요",
  });

  await user.click(screen.getByRole("button", { name: "생성 결과 확인하기" }));

  expect(mockCreateGenerationJob).toHaveBeenCalledWith(
    expect.objectContaining({
      selectedCopyId: "copy_2",
      selectedChannelId: "instagram_story",
      selectedTone: "감성적인",
      userCustomHeadline: "오늘만 만나는 딸기라떼",
      userCustomSubcopy: "신선한 딸기의 달콤함을 담았어요",
    }),
  );
});
```

Orchestrator failing test:

```python
def test_generation_job_restores_selected_ui_values_as_graph_state():
    request = GenerationJobCreateRequest(
        userInput="카페 광고",
        selectedCopyId="copy_2",
        selectedChannelId="instagram_story",
        selectedTone="감성적인",
        userCustomHeadline="오늘만 만나는 딸기라떼",
        userCustomSubcopy="신선한 딸기의 달콤함을 담았어요",
    )

    snapshot = build_generation_job_input_snapshot(request)

    assert snapshot.state_payload["selected_copy_id"] == "copy_2"
    assert snapshot.state_payload["selected_channel_id"] == "instagram_story"
    assert snapshot.state_payload["selected_tone"] == "감성적인"
    assert snapshot.state_payload["user_custom_headline"] == "오늘만 만나는 딸기라떼"
    assert snapshot.state_payload["user_custom_subcopy"] == "신선한 딸기의 달콤함을 담았어요"
```

Files:

```text
apps/web/app/generate/chat/ChatGenerateClient.tsx
apps/web/app/generate/chat/ChatGenerateClient.test.tsx
apps/web/app/api/generation-jobs/route.ts
apps/web/types/marketing.ts
apps/bff/src/app.js
apps/bff/tests/generate.test.js
orchestrator/app/api/schemas/generation_jobs.py
orchestrator/app/generation_jobs/service.py
orchestrator/tests/test_generation_jobs_api.py
orchestrator/tests/test_generation_job_graph_execution.py
```

Commands:

```bash
cd apps/web
npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx

cd ../bff
npm test -- tests/generate.test.js

cd ../..
uv run python -m pytest orchestrator/tests/test_generation_jobs_api.py orchestrator/tests/test_generation_job_graph_execution.py
```

Expected result:

- UI selection values are visible in graph state.
- Copy/channel/tone choices can influence graph execution rather than only appearing in debug metadata.

Commit:

```bash
git add apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx apps/web/app/api/generation-jobs/route.ts apps/web/types/marketing.ts apps/bff/src/app.js apps/bff/tests/generate.test.js orchestrator/app/api/schemas/generation_jobs.py orchestrator/app/generation_jobs/service.py orchestrator/tests/test_generation_jobs_api.py orchestrator/tests/test_generation_job_graph_execution.py
git commit -m "feat(generation): send selected ui values to graph state"
```

---

### Step 5. Support Final Graph Interrupt Types In UI

Purpose: backend graph can interrupt for more than missing context questions. The UI should handle final generation job interrupts by type.

- [x] Add interrupt parser for:
  - `option_question`
  - `copy_candidate_selection`
  - `custom_copy_input`
- [x] Render a selection UI for `copy_candidate_selection`.
- [x] Render headline/subcopy inputs for `custom_copy_input`.
- [x] Submit resume payload through the existing answer/resume generation job endpoint.
- [x] Preserve thread/job identifiers across interrupt resume.
- [x] Add user-facing error state if an unknown interrupt type arrives.

Interrupt parser failing tests:

```ts
it("parses copy candidate selection interrupts", () => {
  expect(parseGenerationJobInterrupt({
    type: "copy_candidate_selection",
    candidates: [{ id: "copy_1", headline: "오늘만 할인" }],
    recommended_candidate_id: "copy_1",
  })).toMatchObject({
    type: "copy_candidate_selection",
    recommendedCandidateId: "copy_1",
  });
});

it("parses custom copy input interrupts", () => {
  expect(parseGenerationJobInterrupt({
    type: "custom_copy_input",
    fields: ["headline", "subcopy"],
  })).toMatchObject({
    type: "custom_copy_input",
    fields: ["headline", "subcopy"],
  });
});
```

UI failing test:

```ts
it("resumes generation job with the selected copy candidate", async () => {
  render(<GenerationJobInterruptStep interrupt={copySelectionInterrupt} />);

  await user.click(screen.getByRole("button", { name: "오늘만 할인 선택" }));

  expect(mockAnswerGenerationJob).toHaveBeenCalledWith(
    expect.objectContaining({
      selectedCopyId: "copy_1",
    }),
  );
});
```

Files:

```text
apps/web/lib/generation-job-interrupt.ts
apps/web/lib/generation-job-interrupt.test.ts
apps/web/components/generate/GenerationJobInterruptStep.tsx
apps/web/app/generate/chat/ChatGenerateClient.tsx
apps/web/app/generate/chat/ChatGenerateClient.test.tsx
apps/web/types/marketing.ts
```

Commands:

```bash
cd apps/web
npm test -- --run lib/generation-job-interrupt.test.ts app/generate/chat/ChatGenerateClient.test.tsx
```

Expected result:

- Final graph can stop for copy selection or custom copy input.
- UI can answer and resume the same job.
- Coverage rows for copy/custom interrupt can move to connected after proof.

Commit:

```bash
git add apps/web/lib/generation-job-interrupt.ts apps/web/lib/generation-job-interrupt.test.ts apps/web/components/generate/GenerationJobInterruptStep.tsx apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx apps/web/types/marketing.ts
git commit -m "feat(generation): handle graph job copy interrupts"
```

---

### Step 6. Show Validation Feedback From Graph Results

Purpose: graph validation nodes should be visible to users in a non-technical way when results are generated.

- [x] Read `validation_summary` from generation job result payload.
- [x] Add `ValidationSummaryPanel` with friendly labels:
  - background check
  - safe area check
  - readability check
  - final validation
- [x] Hide the panel if no validation data exists.
- [x] Use non-technical text. Avoid exposing node names such as `safe_area_gate` or `background_validation`.
- [x] Add result screen tests for pass/warn/fail states.

Failing test:

```ts
it("shows validation feedback when generation result includes validation_summary", () => {
  render(
    <GenerationCompleteStep
      result={{
        imageUrl: "/generated/result.png",
        validationSummary: {
          background: { status: "pass" },
          safeArea: { status: "warn", message: "문구가 가장자리에 가까워요" },
          readability: { status: "pass" },
          final: { status: "warn" },
        },
      }}
    />,
  );

  expect(screen.getByText("결과 확인")).toBeInTheDocument();
  expect(screen.getByText("문구가 가장자리에 가까워요")).toBeInTheDocument();
});
```

Files:

```text
apps/web/components/generate/ValidationSummaryPanel.tsx
apps/web/components/generate/GenerationCompleteStep.tsx
apps/web/app/generate/chat/ChatGenerateClient.test.tsx
apps/web/types/marketing.ts
```

Commands:

```bash
cd apps/web
npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected result:

- Generated result screen can explain validation state without developer terms.
- `validation.feedback-visible` coverage can move to connected.

Commit:

```bash
git add apps/web/components/generate/ValidationSummaryPanel.tsx apps/web/components/generate/GenerationCompleteStep.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx apps/web/types/marketing.ts
git commit -m "feat(generation): show graph validation feedback"
```

---

### Step 7. Update Coverage To Connected Only After Proof

Purpose: after implementation, coverage should represent tested reality.

- [x] Move each completed row from `disconnected` to `connected`.
- [x] Include test evidence references in coverage metadata:
  - test file path
  - state field name
  - UI route/component
- [x] Add a test that blocks connected status when the evidence list is empty.
- [x] Add a summary test that expected gaps are zero for the selected scope.

Failing-to-passing test:

```ts
it("has no uncovered graph capabilities for first-phase ui integration scope", () => {
  const uncovered = getUiOrchestratorRouteCoverage().filter(
    (row) => row.phase === "graph-integration-v1" && row.status !== "connected",
  );

  expect(uncovered).toEqual([]);
});
```

Files:

```text
apps/web/lib/ui-graph-coverage.ts
apps/web/lib/ui-graph-coverage.test.ts
apps/web/lib/ui-orchestrator-route-coverage.ts
apps/web/lib/ui-orchestrator-route-coverage.test.ts
```

Commands:

```bash
cd apps/web
npm test -- --run lib/ui-graph-coverage.test.ts lib/ui-orchestrator-route-coverage.test.ts
```

Expected result:

- Coverage matrix shows graph integration v1 as connected.
- Any later regression in UI/API/state mapping fails tests.

Commit:

```bash
git add apps/web/lib/ui-graph-coverage.ts apps/web/lib/ui-graph-coverage.test.ts apps/web/lib/ui-orchestrator-route-coverage.ts apps/web/lib/ui-orchestrator-route-coverage.test.ts
git commit -m "test(generation): verify ui graph integration coverage"
```

---

### Step 8. Run End-To-End Verification Commands

Purpose: prove the integration across frontend, BFF, and orchestrator.

Commands:

```bash
cd apps/web
npm test -- --run \
  app/generate/chat/ChatGenerateClient.test.tsx \
  lib/api-client.test.ts \
  lib/generation-request-context.test.ts \
  lib/generation-job-interrupt.test.ts \
  lib/ui-graph-coverage.test.ts \
  lib/ui-orchestrator-route-coverage.test.ts

npx tsc --noEmit

cd ../bff
npm test -- tests/generate.test.js

cd ../..
uv run python -m pytest \
  orchestrator/tests/test_generation_jobs_api.py \
  orchestrator/tests/test_generation_job_graph_execution.py
```

Expected result:

- Web tests pass.
- Web typecheck passes.
- BFF tests pass.
- Orchestrator tests pass.

If a test fails:

- [ ] Identify whether the failure is from this branch or pre-existing dirty work.
- [ ] Fix branch-caused failure in the smallest relevant step.
- [ ] If failure is unrelated, document exact failing command and failing test name in the final report.

---

## Manual QA Checklist

- [ ] 대화로 시작해서 정보가 부족하면 질문 UI가 이어진다.
- [ ] 사진 업로드로 시작한 요청이 최종 생성 결과에서도 업로드 사진을 참조한다.
- [ ] 직접 레퍼런스 이미지를 첨부하면 최종 생성 요청 payload에 `referenceImagePath`가 들어간다.
- [ ] 레퍼런스 템플릿을 고르면 `selectedReferenceTemplateId`가 최종 생성 job까지 유지된다.
- [ ] AI 추천 문구 선택값이 최종 생성 job state로 전달된다.
- [ ] 직접 입력한 메인/보조 문구가 최종 생성 job state로 전달된다.
- [ ] 최종 graph가 문구 선택을 요구하면 UI에서 고르고 resume할 수 있다.
- [ ] 최종 graph가 직접 문구 입력을 요구하면 UI에서 입력하고 resume할 수 있다.
- [ ] 생성 결과 화면에서 실제 이미지가 없으면 mock 결과 카드를 보여주지 않는다.
- [ ] 생성 결과 화면에서 validation summary가 있으면 유저 친화적인 검수 안내가 보인다.

---

## Commit Plan

Use separate commits so review can follow the integration one piece at a time.

```text
test(generation): expose ui graph coverage gaps
feat(generation): preserve photo source image for graph jobs
feat(generation): connect direct reference image input
feat(generation): send selected ui values to graph state
feat(generation): handle graph job copy interrupts
feat(generation): show graph validation feedback
test(generation): verify ui graph integration coverage
```

---

## Out Of Scope For This Plan

- Rewriting LangGraph node logic.
- Changing image generation model algorithms.
- Building the admin reference management screen.
- Reworking Supabase authentication or admin UUID policy.
- R2 upload tooling changes.
- Pricing/usage limit enforcement.

---

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Existing dirty files overlap with target files | Inspect each file before editing and stage only logical changes |
| UI state becomes duplicated across route context and chat state | Define one canonical payload builder in `ChatGenerateClient` |
| Backend accepts fields but graph snapshot drops them | Add orchestrator tests against snapshot/state payload |
| Coverage becomes decorative again | Require evidence fields and tests before connected status |
| User-facing validation text exposes node names | Add tests for friendly text and avoid raw graph node labels |

---

## Completion Criteria

This plan is complete when:

- Photo uploaded image path reaches final generation job graph state.
- Direct reference image path reaches final generation job graph state.
- Selected copy/channel/tone/custom text reach graph state as typed fields.
- UI can handle copy candidate and custom copy graph interrupts.
- Validation summary appears on the result screen when present.
- UI-graph coverage tests prove all v1 graph integration capabilities are connected.
- Web, BFF, and Orchestrator targeted tests pass.
