# EasyAds Web UI

Next.js 기반의 모바일 웹앱 프론트엔드입니다. 현재 구현 범위는 C 시나리오의 "대화로 시작하기" 플로우이며, 사용자가 광고 요청을 대화처럼 입력하면 문구 후보를 고르고 광고 브리프를 확인하는 흐름까지 연결되어 있습니다.

## 구현 범위

- `/generate/chat` 모바일 웹앱 화면
- 390x844 뷰포트를 주 기준으로 구현
- 보조 확인 기준: 375x667, 430x932
- 단계별 UI
  1. 원하는 광고 요청 입력
  2. AI가 해석한 정보 확인
  3. 문구 고르기
  4. 브리프 확인 및 광고 생성 CTA
- BFF API 연결
- BFF 또는 백엔드가 꺼져 있을 때도 화면을 확인할 수 있는 로컬 fallback 플로우

## 구조

```text
apps/web
├── app/generate/chat
│   ├── ChatGenerateClient.tsx
│   └── page.tsx
├── components/generate
│   ├── ChatComposer.tsx
│   ├── ChatHeader.tsx
│   ├── ChatMessageList.tsx
│   ├── ChatProgress.tsx
│   ├── CopySelectionPanel.tsx
│   ├── DraftBriefPanel.tsx
│   ├── PromptInputPanel.tsx
│   └── QuickStartChips.tsx
├── lib
│   ├── api-client.ts
│   └── chat-flow.ts
└── e2e
    └── chat-start.spec.ts
```

주요 역할은 다음과 같습니다.

- `ChatGenerateClient.tsx`: 대화형 생성 플로우의 클라이언트 상태와 화면 전환을 담당합니다.
- `api-client.ts`: BFF API 호출을 담당합니다.
- `chat-flow.ts`: 프론트 fallback 플로우와 화면용 데이터 변환을 담당합니다.
- `components/generate/*`: 모바일 UI 구성 요소입니다.
- `e2e/chat-start.spec.ts`: Playwright 기반 모바일 뷰포트 스모크 테스트입니다.

## 백엔드 연결 흐름

```text
Browser
  -> apps/web
  -> apps/bff
  -> orchestrator
```

프론트엔드는 `NEXT_PUBLIC_BFF_BASE_URL` 환경변수로 BFF 주소를 받습니다. 값이 없으면 기본값으로 `http://127.0.0.1:4000`을 사용합니다.

현재 사용하는 BFF API는 다음과 같습니다.

```http
POST /api/generate/chat/start
```

요청 예시:

```json
{
  "userInput": "삼겹살집 회식 손님 많이 오게 포스터 만들어줘",
  "adFormat": "poster"
}
```

```http
POST /api/generate/chat/brief
```

요청 예시:

```json
{
  "jobId": "job-id",
  "threadId": "thread-id",
  "selectedCopyId": "copy-1",
  "selectedChannel": "instagram",
  "context": {
    "businessType": "음식점",
    "goal": "방문 유도"
  }
}
```

## 프론트만 실행하기

화면 UI만 빠르게 확인할 때 사용합니다. 백엔드가 꺼져 있어도 fallback 데이터로 플로우를 볼 수 있습니다.

```bash
cd apps/web
npm install
npm run dev
```

브라우저에서 다음 주소를 엽니다.

```text
http://localhost:3000/generate/chat
```

## 백엔드까지 연결해서 실행하기

터미널 3개를 사용합니다. 예시는 8010 포트를 사용합니다. 로컬에서 8000 또는 8001 포트가 이미 사용 중일 수 있어서 충돌을 피하기 위한 값입니다.

터미널 1: orchestrator 실행

```bash
uv run uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8010
```

터미널 2: BFF 실행

```bash
cd apps/bff
npm install
ORCHESTRATOR_BASE_URL=http://127.0.0.1:8010 PORT=4000 npm run dev
```

터미널 3: Web 실행

```bash
cd apps/web
npm install
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000 npm run dev
```

브라우저에서 다음 주소를 엽니다.

```text
http://localhost:3000/generate/chat
```

## 모바일 기준으로 확인하기

Chrome DevTools의 Toggle device toolbar를 켜고 다음 크기를 확인합니다.

- 375x667
- 390x844
- 430x932

현재 디자인의 주 기준은 390x844입니다. 데스크톱 브라우저에서 열어도 모바일 앱 화면처럼 중앙에 고정된 프레임으로 보이도록 구현되어 있습니다.

## 검증 명령어

```bash
cd apps/web
npm run lint
npm run test
npm run build
```

Playwright E2E:

```bash
cd apps/web
npm run e2e
```

백엔드 연결까지 확인하려면 orchestrator와 BFF를 먼저 켠 뒤 E2E를 실행합니다.

## 작업 흐름

1. UI만 바꿀 때는 `components/generate/*`와 `ChatGenerateClient.tsx`를 먼저 확인합니다.
2. 화면 상태나 fallback 응답을 바꿀 때는 `lib/chat-flow.ts`를 같이 수정합니다.
3. API 요청/응답 필드가 바뀌면 `lib/api-client.ts`, `apps/bff`, `orchestrator` 계약을 함께 맞춥니다.
4. 모바일 기준 3개 뷰포트에서 레이아웃을 확인합니다.
5. `npm run test`, `npm run build`, 필요하면 `npm run e2e`를 실행합니다.

## 현재 주의할 점

- 프론트는 BFF 호출이 실패하면 로컬 fallback 플로우로 계속 진행합니다. 그래서 화면이 정상 동작한다고 해서 항상 백엔드 연결이 성공한 것은 아닙니다.
- 실제 이미지 생성 프로덕션 플로우가 완전히 연결된 상태는 아닙니다. 현재는 대화 시작, 문구 후보, 브리프 확인까지의 API 연결이 구현되어 있습니다.
- 시나리오 참고 자료는 루트의 `images/` 아래에 있고, 프론트에서 직접 사용하는 정적 참고 파일은 `apps/web/public/scenarios` 아래에 있습니다.
