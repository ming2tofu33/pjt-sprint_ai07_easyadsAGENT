# PR #44 UI/UX QA Checklist

> QA date: 2026-06-02  
> Branch: `feat/fe/generation-mock-cleanup`  
> Target PR: `#44 [feat/fe] 생성 결과와 레퍼런스 플로우 실제 데이터 연결`  
> Default QA mode: mock LLM/T2I  
> Final paid smoke: `gpt-image-1` golden path only

## 1. Environment Readiness

- [ ] `git status --short --branch` shows the expected branch and no unexpected tracked modifications.
- [ ] `origin/develop` is fetched before QA starts.
- [ ] Existing dev servers on `3001`, `4001`, and `8011` are stopped before launching the QA stack.
- [ ] Orchestrator starts on `8011` with mock external generation settings.
- [ ] BFF starts on `4001` with `ORCHESTRATOR_BASE_URL=http://127.0.0.1:8011`.
- [ ] Web starts on `3001` with `NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4001`.
- [ ] `GET http://127.0.0.1:8011/health` returns `{"status":"ok"}`.
- [ ] `GET http://127.0.0.1:4001/health` returns `{"status":"ok"}`.
- [ ] `HEAD http://127.0.0.1:3001/generate/chat` returns HTTP `200`.

## 2. Automated Regression Checks

- [ ] `cd apps/web && npm test` passes.
- [ ] `cd apps/web && npx tsc --noEmit --pretty false` passes.
- [ ] `cd apps/bff && npm test -- tests/generate.test.js` passes.
- [ ] `uv run python -m pytest orchestrator/tests/test_chat_api.py` passes.
- [ ] `uv run python -m pytest orchestrator/tests/test_api_generation_jobs_router.py orchestrator/tests/test_gpt_image2_quality_batch_script.py` passes.
- [ ] Existing React `act(...)` warnings are recorded as warnings, not test failures.
- [ ] Existing Python deprecation warnings are recorded as warnings, not test failures.

## 3. Chat Generation Flow

- [ ] Enter an incomplete request such as `인스타 할인 광고 만들어줘`.
- [ ] The UI asks for missing context instead of jumping to a fixed mock result.
- [ ] Answer business type, product/service, and promotion goal questions.
- [ ] The "현재까지 파악한 내용" panel updates after each answer.
- [ ] The question loop does not repeat the same accepted answer indefinitely.
- [ ] The "AI가 이렇게 이해했어요" screen reflects the user input and backend response.
- [ ] The "문구 고르기" button becomes enabled only after required context is ready.
- [ ] The copy candidates match the request topic and are not static sample copy.

## 4. Copy Generation Modes

- [ ] `문구도 추천` shows selectable backend copy candidates.
- [ ] `AI 자동 완성` skips manual copy selection when the backend returns a ready brief.
- [ ] `이미지만 생성` skips copy selection and still produces a valid brief/result state.
- [ ] `직접 문구` sends `userCustomHeadline` to the request payload.
- [ ] Direct subcopy sends `userCustomSubcopy` when provided.
- [ ] Direct copy text appears in the brief and result screens.
- [ ] Long direct copy wraps without overlapping buttons or the input card.

## 5. Brief Confirmation

- [ ] "AI가 브리프를 정리했어요" uses the selected context, copy, tone, and channel.
- [ ] Business type, product/service, purpose, selected copy, tone, and channel match previous selections.
- [ ] Recommended image direction is related to the selected product/service.
- [ ] The CTA button leads to generation result state without showing fixed sample copy.

## 6. Generated Result Screen

- [ ] When `finalImagePath` exists, the screen shows "찰떡 광고 시안이 완성됐어요".
- [ ] The result card has the `실제 생성` badge.
- [ ] The rendered image `src` includes `/api/generated-assets?path=`.
- [ ] The result does not crop in a visibly broken way at `390x844`.
- [ ] If `finalImagePath` is missing, the screen shows "이미지 생성이 완료되지 않았어요".
- [ ] If `finalImagePath` is missing, no generated asset image is rendered.
- [ ] Download stays disabled or shows the connected mock notice when no public download URL exists.
- [ ] "세션 보관함에서 보기" opens the archive screen.

## 7. Reference Gallery Flow

- [ ] The reference gallery loads templates from the API.
- [ ] Temporary reference templates display the development notice.
- [ ] Search filters the gallery without crashing.
- [ ] Category filters update the list without stale results.
- [ ] Selecting `수박주스 블루 여름 피드` moves to chat start.
- [ ] The chat input is prefilled with `수박주스 블루 여름 피드 스타일로 광고 만들어줘`.
- [ ] The chat start request includes `selectedReferenceTemplateId`.
- [ ] The selected reference template is preserved through the generation request.

## 8. Photo Generation Flow

- [ ] PNG upload is accepted.
- [ ] JPG upload is accepted.
- [ ] WebP upload is accepted.
- [ ] Unsupported file type shows "PNG, JPG, WebP 형식의 사진만 사용할 수 있어요."
- [ ] Selected image preview appears in the upload card.
- [ ] Long photo prompt expands the textarea without clipping previous text.
- [ ] `/api/generate/photo/upload` returns `sourceImagePath`.
- [ ] `/api/generate/photo/start` receives the same `sourceImagePath`.
- [ ] Photo generation continues into the same copy/brief/result flow as chat generation.

## 9. Archive Flow

- [ ] Generated results appear under "최근 실제 생성".
- [ ] Sample ads are separated under "샘플 광고".
- [ ] Archive empty state appears when no generated results exist.
- [ ] Clicking a generated item opens that exact item.
- [ ] Clicking a generated item does not open the latest generated item by mistake.
- [ ] The generated image viewer title is "생성 이미지 보기".
- [ ] The generated image viewer says "생성된 이미지만 확인하고 다운로드할 수 있어요."
- [ ] The archive more menu exposes view, similar-generation, download notice, and delete actions.
- [ ] Delete removes the selected generated item from the session archive.

## 10. Mobile UI/UX Pass

- [ ] `390x844` viewport has no overlapping chat bubbles, inputs, or bottom buttons.
- [ ] `375x667` viewport has no inaccessible primary CTA.
- [ ] `430x932` viewport keeps visual rhythm and button spacing.
- [ ] Long Korean words do not overflow buttons.
- [ ] Chat input with multiple lines remains readable.
- [ ] Generated result image frame keeps a stable aspect ratio.
- [ ] Bottom navigation does not cover the active form field.
- [ ] Loading, error, empty, and success states are visually distinct.

## 11. Optional Paid Golden Path

- [ ] Confirm `OPENAI_API_KEY` is set.
- [ ] Start Orchestrator with `T2I_DEFAULT_ENGINE=gpt_image_2`.
- [ ] Pin the actual model with `T2I_GPT_IMAGE_MODEL=gpt-image-1`.
- [ ] Enable guarded external image generation with `T2I_ALLOW_API_CALLS=true`, `EASYADS_ENABLE_EXTERNAL_T2I=true`, and `EASYADS_ENABLE_GPT_IMAGE_2=true`.
- [ ] Run one chat-based generation with a complete prompt.
- [ ] Run one photo-based generation only if budget allows.
- [ ] Confirm the result still renders through `/api/generated-assets?path=`.
- [ ] Record the generated job id and output path in the QA notes.

## 12. QA Notes

Record findings in this format:

```text
Finding:
Severity: P0 | P1 | P2 | P3
Flow:
Viewport:
Steps:
Expected:
Actual:
Screenshot:
Owner:
Resolution:
```
