# 내 사진으로 만들기 source asset 흐름 정리 작업 요약 (2026-06-15)

> **브랜치:** `fix/fe/photo-source-asset-flow` -> **PR #193 (base: develop)**
> **주요 구현 커밋:** `be9877a1 fix(fe): route photo flow through source assets`
> **결과:** 웹 타입체크 통과, 관련 Vitest **170 passed**, Playwright + mock Orchestrator/R2 runtime smoke 통과
> **핵심 한 줄:** `내 사진으로 만들기`가 legacy `photo/start + sourceImagePath + photo_..._thread` 길로 빠지던 것을, 정식 `generation-jobs + sourceAssetId + thread_...` 흐름으로 합쳤습니다.

---

## 이 작업이 왜 필요했나 (배경)

`docs/iti흐름.md`에서 정리한 것처럼, 사진을 첨부해 광고 이미지를 만드는 플로우는 다른 생성 플로우와 구조가 달랐습니다.

- `대화로 시작하기`와 `샘플 템플릿 시작`은 주로 `/api/generation-jobs`를 타고, 정식 작업방 ID인 `thread_...`와 연결됩니다.
- `내 사진으로 만들기`는 `/api/generate/photo/start` -> `/v1/marketing/photo/start`를 타고, `photo_..._thread`를 만들었습니다.
- 최종 이미지 생성 단계에서는 프론트가 `sourceImagePath`를 보내고, Next route가 `source_image_path`로 바꿔 보냈습니다.
- 그런데 Orchestrator public generation job schema는 `source_image_path`와 `reference_image_path`를 public API 입력으로 받지 않도록 막고 있습니다.

그래서 실제 증상은 두 갈래로 나올 수 있었습니다.

1. 사진 시작 대화가 정식 generation job 작업방이 아니어서 질문 답변/복원/삭제 로직이 다른 플로우와 다르게 움직임
2. 최종 생성에서 `source_image_path`가 schema validation에 걸려 i2i 생성 요청이 실패할 수 있음

> 쉽게 말하면: 일반 주문은 모두 "주문번호 `thread_...` + 등록된 상품 사진 asset"으로 주방에 들어가는데, 사진 주문만 "임시 메모지 `photo_..._thread` + 로컬 파일 경로"로 옆문에 들어가던 상황입니다. 주방 시스템은 이제 정식 주문번호와 등록된 asset만 믿도록 바뀌었는데, 사진 주문만 옛 메모지를 들고 와서 막히던 셈입니다.

---

## 1. 사진 업로드를 source asset 등록까지 확장

**파일:** `apps/web/lib/api-client.ts`

**무엇을:** `uploadPhotoAsset(file)`이 이제 두 가지 일을 함께 합니다.

1. 기존 로컬 업로드 유지: `/api/generate/photo/upload`
   - 반환값: `sourceImagePath`
   - 용도: 기존 미리보기/로컬 분석 호환
2. 신규 source asset 업로드: `/api/assets/uploads/presign` -> R2 `PUT` -> `/complete`
   - 요청: `kind: "source"`
   - 반환값: `sourceAssetId`
   - 용도: 정식 generation job graph state 입력

**왜:** public generation job schema가 로컬 path를 직접 받지 않으므로, 사진 원본은 `sourceAssetId`로 전달해야 합니다. 다만 프론트 일부 상태와 기존 preview 경로는 아직 `sourceImagePath`를 참고하므로, 로컬 path는 보조값으로만 남겼습니다.

> 쉽게 말하면: 사진 파일을 "책상 위 임시 파일"로만 두지 않고, 물류 시스템에 정식 등록해 asset 번호를 받도록 바꾼 겁니다. 화면 미리보기용 종이 영수증은 남기되, 실제 주방 지시는 asset 번호로만 합니다.

---

## 2. 사진 시작을 `photo/start`가 아니라 `generation-jobs`로 전환

**파일:** `apps/web/app/generate/chat/ChatGenerateClient.tsx`

**무엇을:** `내 사진으로 만들기` 시작 버튼을 눌렀을 때 더 이상 `startPhotoGeneration()`을 호출하지 않습니다. 대신 `createGenerationJob()`으로 바로 정식 generation job을 만듭니다.

핵심 payload:

```ts
{
  entryMode: "photo_start",
  runMode: "graph_job",
  sourceAssetId,
  sourceImagePath: undefined,
  metadata: {
    source: "web_photo_intake",
    source_asset_id: sourceAssetId,
    source_image_path: null,
    selected_engine,
    requested_engine,
    t2i_engine,
    selected_engine_label
  }
}
```

**왜:** 시작 단계부터 정식 generation job으로 들어가야 이후 질문 답변, thread 복원, 삭제, 최종 생성이 모두 같은 작업방 체계를 씁니다.

**보호 장치:** 사진 업로드 결과에 `sourceAssetId`가 없으면 다음 단계로 진행하지 않고, "사진을 다시 업로드해 주세요" 메시지로 실패시킵니다.

> 쉽게 말하면: 사진 주문도 처음부터 일반 주문 접수대에서 `thread_...` 주문번호를 받게 했습니다. 옛 옆문(`photo/start`)은 UI에서 더 이상 쓰지 않습니다.

---

## 3. 최종 이미지 생성도 source asset id를 끝까지 보존

**파일:** `ChatGenerateClient.tsx`, `chat-flow.ts`, `chat-snapshots.ts`, `generated-creative-storage.ts`, `chat-thread-state-mapper.ts`, `types/marketing.ts`

**무엇을:** `sourceAssetId`를 프론트 상태, turn snapshot, flow snapshot, 생성 결과 snapshot, thread restore mapper에 모두 추가했습니다.

최종 생성 버튼을 누를 때는 다음 규칙을 적용합니다.

- `sourceAssetId`가 있으면 `sourceImagePath`는 보내지 않음
- `sourceImagePath`만 있고 `sourceAssetId`가 없으면 명시적으로 에러 처리
- metadata에는 추적용으로 `source_asset_id`를 남기고, `source_image_path`는 `null`로 고정

**왜:** 사진 시작에서 얻은 source asset id가 중간 화면 이동, 새로고침, 브리프 확인, 최종 생성까지 살아 있어야 i2i 생성이 같은 원본 사진을 참조할 수 있습니다.

> 쉽게 말하면: 접수할 때 받은 asset 번호가 브리프 종이, 작업방 복원 기록, 최종 주방 지시서까지 계속 따라다니게 한 겁니다. 중간에 번호가 사라지면 옛 로컬 파일 경로로 되돌아가지 않고, 다시 업로드하라고 멈춥니다.

---

## 4. Next route 계약을 asset id 기준으로 확장

**파일:** `apps/web/app/api/_schemas/generate.ts`, `apps/web/app/api/generation-jobs/route.ts`

**무엇을:** `/api/generation-jobs` Next route가 camelCase 입력을 Orchestrator용 snake_case로 바꿀 때 `sourceAssetId`와 `referenceAssetId`도 함께 처리하도록 했습니다.

```ts
payload.source_asset_id = payload.source_asset_id ?? payload.sourceAssetId;
payload.reference_asset_id = payload.reference_asset_id ?? payload.referenceAssetId;
delete payload.sourceAssetId;
delete payload.referenceAssetId;
```

Zod schema에도 `source_asset_id`, `sourceAssetId`, `reference_asset_id`, `referenceAssetId`를 허용했습니다.

**왜:** FE 코드는 camelCase를 쓰고, Orchestrator public API는 snake_case를 씁니다. 이 변환이 route에 없으면 FE에서 `sourceAssetId`를 잘 들고 있어도 백엔드는 값을 받지 못합니다.

> 쉽게 말하면: 프론트가 "assetId"라고 적어 보낸 송장을 백엔드가 알아듣는 "asset_id" 양식으로 바꿔주는 접수 담당자를 추가한 겁니다.

---

## 5. route coverage 문서성 코드도 새 계약으로 갱신

**파일:** `apps/web/lib/ui-orchestrator-route-coverage.ts`

**무엇을:** 기존 coverage 표는 "사진 기반 최종 생성이 `source_image_path`를 graph state로 전달한다"고 설명하고 있었습니다. 실제 계약은 이제 `source_asset_id`이므로 설명과 graph state field를 갱신했습니다.

**왜:** 이 표는 팀원이 UI -> API -> graph 연결 상태를 빠르게 확인하는 문서성 코드입니다. 코드가 바뀌었는데 표가 옛 path 계약을 말하면 다음 작업자가 다시 같은 방향으로 오해할 수 있습니다.

> 쉽게 말하면: 운영 매뉴얼에서도 "로컬 파일 경로를 들고 가세요"라는 옛 문구를 지우고, "asset 번호를 들고 가세요"로 바꾼 겁니다.

---

## 검증 결과 요약

### 자동 테스트

웹 패키지 기준으로 확인했습니다.

```bash
npx tsc --noEmit --pretty false
npx vitest run lib/api-client.test.ts lib/chat-flow.test.ts lib/chat-thread-state-mapper.test.ts lib/ui-orchestrator-route-coverage.test.ts app/api/generate/chat/routes.test.ts app/generate/chat/ChatGenerateClient.test.tsx
```

결과:

- TypeScript typecheck 통과
- 관련 Vitest **170 passed**
- 기존 `StudioEntryStep` 관련 React `act(...)` warning은 계속 출력되지만 실패는 없음

### 브라우저 runtime smoke

Playwright + mock Orchestrator/R2로 실제 브라우저에서 다음 흐름을 확인했습니다.

1. `/generate/photo` 진입
2. 사진 파일 업로드
3. `GPT-image-2` 선택
4. 사진 기반 생성 시작
5. source asset presign 요청
6. R2 `PUT`
7. asset complete
8. photo start generation job 생성
9. final generation job 생성
10. 완료 화면 진입

확인한 핵심 값:

- presign 요청: `kind: "source"`
- R2 PUT 발생: 이미지 bytes 전송 확인
- legacy `/api/v1/marketing/photo/start` 호출: **0회**
- photo start job:
  - `entryMode: "photo_start"`
  - `runMode: "graph_job"`
  - `source_asset_id` 포함
  - top-level `source_image_path` 없음
- final generation job:
  - `threadId: "thread_photo_start"`
  - `source_asset_id` 유지
  - top-level `source_image_path` 없음
  - metadata의 `source_image_path`는 `null`

---

## PR 안내 (#193)

PR: `https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/pull/193`

- base: `develop`
- head: `fix/fe/photo-source-asset-flow`
- 변경 파일: 13개
- 주요 구현 커밋: `be9877a1`

현재 브랜치 `fix/srv/ad-compliance-suggestions`에는 develop에 아직 없는 compliance 커밋들이 섞여 있었습니다. 그래서 이번 사진 플로우 수정은 `origin/develop`에서 새 브랜치를 따서 cherry-pick성으로 분리했고, PR #193에는 이 작업만 들어가게 했습니다.

---

## 남은 주의점 / 다음 작업

1. **실환경 smoke는 별도 필요**
   - 이번 runtime smoke는 mock Orchestrator/R2 기반입니다.
   - FE -> Next route -> asset upload 계약 -> generation job payload 연결은 확인했지만, 실제 R2 bucket과 실제 이미지 모델 호출은 staging/실서비스 환경에서 한 번 더 확인해야 합니다.

2. **legacy API 정리 여부 결정**
   - `startPhotoGeneration()`과 `/api/generate/photo/start` route는 아직 코드에 남아 있습니다.
   - UI는 더 이상 사용하지 않지만, 다른 QA 스크립트나 외부 호출자가 있는지 확인한 뒤 제거 여부를 결정하는 게 안전합니다.

3. **QA smoke 스크립트 업데이트 후보**
   - 기존 `apps/web/scripts/qa-generation-flow-smoke.js`의 photo smoke는 legacy `/api/generate/photo/start`를 기다리는 형태였습니다.
   - 정식 QA 스크립트로 계속 쓸 거라면 `/api/generation-jobs` 기반 기대값으로 갱신해야 합니다.

4. **질문 반복/삭제 증상 재확인**
   - 이번 수정의 구조적 목표는 `photo_..._thread` 분리 문제를 없애는 것입니다.
   - staging에서 실제 `promotion_goal` 질문 답변과 휴지통 삭제까지 한 번 연결 확인하면 `docs/iti흐름.md`의 의심 지점을 완전히 닫을 수 있습니다.
