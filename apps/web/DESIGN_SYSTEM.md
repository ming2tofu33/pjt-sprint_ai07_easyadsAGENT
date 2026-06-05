# EasyAds Web Design System

EasyAds Web은 모바일 웹앱을 390x844 화면 기준으로 먼저 설계합니다. 데스크톱에서는 실제 서비스 화면을 넓히지 않고, 모바일 앱 프레임을 중앙에 보여주는 방식으로 확인합니다.

## Design Direction

- **Style:** 밝은 모바일 앱, 부드러운 카드, 선명한 검정 CTA, 라임/퍼플/민트/코랄 포인트
- **Primary viewport:** 390x844
- **Secondary viewports:** 375x667, 430x932
- **Interaction baseline:** 모든 주요 터치 타깃은 최소 44px
- **Motion:** 짧은 press feedback과 방향성 있는 onboarding slide motion만 사용

## Token Layers

토큰은 `app/globals.css`의 `:root`에 정의합니다. 기존 화면을 점진적으로 옮기기 위해 `--color-text`, `--color-border` 같은 legacy alias도 당분간 유지합니다.

### Base Tokens

```css
--color-bg-page
--color-bg-surface
--color-bg-card
--color-text-primary
--color-text-secondary
--color-text-muted
--color-text-inverse
--color-border-soft
--color-border-frame
```

기본 화면, 카드, 텍스트, 경계선에 사용하는 토큰입니다. 새 UI를 만들 때는 raw hex 대신 이 토큰부터 사용합니다.

### Brand Tokens

```css
--color-brand-lime
--color-brand-lime-soft
--color-brand-lime-shell
--color-brand-purple
--color-brand-purple-soft
--color-brand-purple-shell
--color-brand-mint
--color-brand-mint-border
--color-brand-coral
--color-brand-coral-soft
```

라임은 앱의 핵심 액센트, 퍼플은 포커스/AI/진행 상태, 민트는 알림/성공 보조, 코랄은 결과/저장/주의성 피드백에 사용합니다.

### Status Tokens

```css
--color-status-success
--color-status-success-soft
--color-status-warning
--color-status-danger
--color-status-danger-soft
```

완료, 경고, 실패 상태에 사용합니다. 색상만으로 의미를 전달하지 말고 아이콘이나 텍스트를 함께 둡니다.

### Shape, Layout, Motion Tokens

```css
--radius-sm
--radius-md
--radius-lg
--radius-xl
--radius-phone
--radius-pill
--space-1 ... --space-7
--touch-target-min
--mobile-shell-width
--mobile-shell-min-height
--screen-padding-x
--screen-padding-top
--screen-padding-bottom
--shadow-phone
--shadow-card
--motion-press
--motion-slide
```

카드는 보통 `--radius-md` 또는 `--radius-lg`를 사용합니다. 큰 안내/온보딩 패널은 `--radius-xl`까지 허용합니다. 버튼 press motion은 `--motion-press`, onboarding carousel은 `--motion-slide`를 사용합니다.

## Component Standards

### Buttons

| Class | Use | Visual Rule |
| --- | --- | --- |
| `primaryButton` | 화면의 주 CTA | 검정 배경, 흰 글자, 56px 높이 |
| `secondaryButton` | 보조 CTA | 흰 배경, soft border, 48px 높이 |
| `iconButton` | 뒤로가기/닫기/도구 | 44x44, 투명 배경, 원형 hit area |
| `sendButton` | 입력창 전송 | 검정 원형 버튼 |
| `textButton` | 링크성 보조 액션 | 배경 없이 텍스트 중심 |
| chip/filter buttons | 필터/선택 상태 | pill radius, active는 검정 또는 브랜드 soft tone |

한 화면에는 가능한 하나의 primary CTA만 둡니다. 같은 중요도의 검정 버튼을 여러 개 두지 않습니다.

### Cards

| Pattern | Use | Visual Rule |
| --- | --- | --- |
| `card` | 기본 정보 그룹 | 흰 배경, soft border, card shadow |
| action cards | 시작 방식/메뉴/알림 | 전체 영역 클릭 가능, 44px 이상 |
| preview cards | 광고/샘플 시안 | 콘텐츠 색은 mock art 색상으로 분리 |
| list cards | 설정/사용량/알림 목록 | row divider는 soft border |
| empty/error cards | 예외 상태 | 상태 색 + 회복 액션 CTA |

카드 안에 다시 카드처럼 보이는 큰 framed UI를 중첩하지 않습니다. 반복 아이템, 모달, 실제 도구 패널에만 카드 스타일을 씁니다.

## Color Audit Rules

색상은 세 그룹으로 분류합니다.

### Replace With Tokens

다음 색은 새 코드에서 raw hex로 쓰지 않습니다.

```text
#fff, #ffffff
#111, #111111
#050505
#e8e6df
#eaff79
#f3ffd0, #f5ffd0
#aa92ff
#eee8ff, #f3efff
#dff8f2
#fff0ea
#ffb3a7
```

### Semantic Tokens Required

완료, 실패, 경고, 진행 중, 선택됨, 비활성 상태는 색상 목적이 분명해야 합니다. `--color-status-*`, `--color-brand-*`, `--color-action-*` 중 하나를 우선 사용합니다.

### Allowed As Art Colors

광고 시안 mock, 샘플 포스터, 컵/상품 일러스트, 배경 그라디언트처럼 콘텐츠 자체를 표현하는 색상은 raw hex를 남길 수 있습니다. 단, 버튼/텍스트/경계선/카드 같은 UI 시스템 색으로 재사용하지 않습니다.

### Current Audit Status

1차 토큰 정리에서 다음 UI 시스템 색은 토큰으로 이동했습니다.

```text
액션 검정: --color-action-primary
액션 반전 텍스트: --color-action-primary-text / --color-text-inverse
얇은 divider: --color-border-hairline
control border: --color-border-control
overlay border: --color-border-overlay
progress/track neutral: --color-neutral-track
purple text/accent: --color-brand-purple-strong / --color-brand-purple-text
mint text/accent: --color-brand-mint / --color-brand-mint-text
coral text/accent: --color-brand-coral-soft / --color-brand-coral-text
```

2차 감사에서는 화면 구간별로 남은 UI 구조 색을 추가로 정리했습니다.

```text
card/button/list surface: --color-bg-card
soft border fallback: --color-border-soft
neutral chips and rails: --color-neutral-chip / --color-neutral-track
mint soft surfaces: --color-brand-mint-soft
warning and danger surfaces: --color-status-warning / --color-status-danger
success progress: --color-status-success / --color-status-success-soft
```

아직 남아 있는 `#fff`, `#111`, pastel hex 값은 대부분 아래 성격입니다.

- mock 광고 시안 안의 컵/상품 하이라이트
- 온보딩/대시보드 일러스트의 검정 라인 아트
- 샘플 포스터별 고유 배경 그라디언트
- 상태를 설명하는 소형 mock 그래픽

다음 감사 작업에서는 남은 raw 색을 지울 때 화면별로 먼저 확인합니다. 특히 `#fff`와 `#111`은 일러스트 색으로도 쓰이므로 전역 치환하지 않습니다.

## Screen Layout Rules

### Mobile Shell

- Shell width: `--mobile-shell-width` = 390px
- Shell min-height: `--mobile-shell-min-height` = 760px
- Body padding: `--screen-padding-top` / `--screen-padding-x` / `--screen-padding-bottom`
- Desktop preview: shell remains centered, not stretched

### Header

- Top action buttons are 44x44.
- Screen title is centered when there is a back/action button pair.
- Home/dashboard headers may use left-aligned title when the screen is not a step flow.

### Body

- Section gap should use `--dashboard-section-gap` or the global spacing tokens.
- Body copy should stay at 12px or larger.
- Text should wrap before it overflows. Avoid shrinking text with viewport units.

### Footer And Bottom Tabs

- Primary CTA sits in `stepFooter` or the equivalent bottom action area.
- Bottom tabs have at most five items.
- Active tab uses text/icon color contrast, not only a background change.
- Fixed or sticky bottom UI must leave enough scroll room for content.

## Migration Checklist

When editing or adding a screen:

1. Use tokens from `globals.css` before adding a new raw color.
2. If a new raw color is needed, decide whether it is a UI system color or an art/content color.
3. Use existing `primaryButton`, `secondaryButton`, `iconButton`, `card`, and bottom-tab patterns before creating a new class.
4. Keep touch targets at or above `--touch-target-min`.
5. Check 375x667, 390x844, and 430x932.
6. Run `npm run lint`, `npm run test`, and focused Playwright checks for changed flows.
