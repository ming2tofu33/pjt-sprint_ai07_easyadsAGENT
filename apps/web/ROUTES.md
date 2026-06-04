# EasyAds Web Routes

이 문서는 `apps/web/app` 기준으로 현재 구현된 서비스 화면 주소를 정리합니다. 새 라우트를 추가하거나 주소를 바꾸면 이 파일과 `README.md`의 구현 범위를 함께 갱신합니다.

## Entry

| Route | Screen | Notes |
| --- | --- | --- |
| `/` | 앱 진입 | 온보딩 완료 여부에 따라 `/onboarding` 또는 홈 대시보드 표시 |
| `/onboarding` | 온보딩 가이드 | 한 페이지 안에서 슬라이드 전환 |
| `/onboarding/modes` | 온보딩 호환 주소 | `/onboarding`과 같은 플로우로 연결 |
| `/onboarding/brief` | 온보딩 호환 주소 | `/onboarding`과 같은 플로우로 연결 |
| `/onboarding/start` | 온보딩 호환 주소 | `/onboarding`과 같은 플로우로 연결 |

## Dashboard

| Route | Screen | Notes |
| --- | --- | --- |
| `/studio` | 스튜디오 진입 | 제작 방식 선택 |
| `/reference` | 레퍼런스 갤러리 | 스타일 기반 제작 진입 |
| `/reference/empty` | 레퍼런스 빈 상태 | 예외 상태 UI |
| `/ads` | 보관함 | 저장된 광고 시안 목록 |
| `/ads/empty` | 보관함 빈 상태 | 예외 상태 UI |
| `/brand` | 브랜드 홈 | 브랜드 키트 진입 |
| `/my` | 마이페이지 | 계정/사용량 진입 |
| `/settings` | 앱 설정 | 알림/데이터/계정 설정 |
| `/notifications` | 알림 센터 | 알림 목록 |

## Generate

| Route | Screen | Notes |
| --- | --- | --- |
| `/generate/chat` | 대화로 시작하기 | BFF 연결 + fallback |
| `/generate/chat/generating` | 광고 생성 중 | mock 진행 화면 |
| `/generate/chat/complete` | 생성 완료 | mock 광고 결과 |
| `/generate/chat/similar` | 비슷한 스타일 더보기 | 완료 화면과 왕복 |
| `/generate/chat/failed` | 생성 실패 | 예외 상태 UI |
| `/generate/photo` | 내 사진으로 만들기 | 사진 업로드형 mock 플로우 |
| `/generate/photo/upload-failed` | 사진 업로드 실패 | 예외 상태 UI |

## Reference Style Flow

동적 라우트의 mock id는 `lib/mock-dashboard-data.ts`에 정의된 레퍼런스 id를 사용합니다.

| Route | Screen | Example |
| --- | --- | --- |
| `/reference/[creativeId]` | 레퍼런스 상세 보기 | `/reference/ref-strawberry-poster` |
| `/reference/[creativeId]/analysis` | AI 스타일 분석 | `/reference/ref-strawberry-poster/analysis` |
| `/reference/[creativeId]/similar` | 유사 스타일 추천 | `/reference/ref-strawberry-poster/similar` |
| `/reference/[creativeId]/start` | 이 스타일로 시작하기 | `/reference/ref-strawberry-poster/start` |

현재 확인 가능한 mock id:

```text
ref-strawberry-poster
ref-review-banner
ref-sale-story
ref-spring-sale
```

## Ads Save Flow

동적 라우트의 mock id는 `lib/mock-dashboard-data.ts`에 정의된 광고 결과 id를 사용합니다.

| Route | Screen | Example |
| --- | --- | --- |
| `/ads/[creativeId]` | 결과 상세 확인 | `/ads/result-1` |
| `/ads/[creativeId]/save` | 저장 방식 선택 | `/ads/result-1/save` |
| `/ads/[creativeId]/saved` | 저장 완료 | `/ads/result-1/saved` |

현재 확인 가능한 mock id:

```text
result-1
result-2
result-3
result-4
result-5
result-6
result-7
result-8
```

## Brand Kit

| Route | Screen | Notes |
| --- | --- | --- |
| `/brand/kit` | 브랜드 키트 생성/수정 시작 | 브랜드 핵심 정보 요약 |
| `/brand/kit/info` | 기본 정보 입력 | 업종/대상/혜택 |
| `/brand/kit/tone` | 톤앤매너 설정 | 색감/말투/금지어 |
| `/brand/kit/complete` | 브랜드 키트 완료 | 홈/스튜디오 복귀 |

## Account And Notifications

| Route | Screen | Notes |
| --- | --- | --- |
| `/my/account` | 계정 정보 | 프로필/매장 정보 |
| `/my/usage` | 사용량 관리 | 생성량/저장공간/플랜 |
| `/notifications/settings` | 알림 설정 | 채널/종류별 설정 |
| `/notifications/complete` | 알림 처리 완료 | 성공 상태 UI |
| `/notifications/failed` | 알림 처리 실패 | 예외 상태 UI |

## QA Checklist

주요 주소를 수정한 뒤에는 아래를 확인합니다.

```bash
cd apps/web
npm run lint
npm run test
npm run build
```

모바일 shell 또는 화면 전환이 바뀌었으면 Playwright도 실행합니다.

```bash
cd apps/web
npm run e2e
```
