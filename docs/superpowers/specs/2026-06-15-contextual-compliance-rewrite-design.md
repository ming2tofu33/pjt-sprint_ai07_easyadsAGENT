# 문맥형 광고 규제 문구 제안 설계

작성일: 2026-06-15  
브랜치: `fix/srv/ad-compliance-suggestions`  
목표: 광고 규제 표현이 발견되었을 때, 하드코딩 예시 문구가 아니라 원문 맥락을 유지한 안전 문구 후보를 생성하고 다시 검수한다.

## 배경

현재 광고 규제 검토는 패턴 기반 탐지 자체는 정상적으로 동작하지만, 제안 문구가 규칙 YAML의 `examples[0].safe`에 강하게 의존한다. 그래서 `최고다 고기!`처럼 음식점 문맥의 문구에서도 `고객 만족 코칭 프로그램` 같은 다른 업종 예시가 그대로 노출될 수 있다.

단기 패치는 위험 표현만 순화하는 deterministic rewrite로 문제를 완화하지만, 근본적으로는 규제 탐지와 대안 문구 생성을 분리해야 한다.

## 범위

이번 설계의 2차 목표는 다음까지다.

- 규제 이슈가 발견된 경우에만 LLM 리라이터를 호출한다.
- LLM은 법적 판단을 하지 않고, 이미 탐지된 규칙과 원문 맥락을 바탕으로 안전 후보 문구만 만든다.
- LLM 후보는 다시 기존 `ComplianceService.check_copy()`로 재검수한다.
- 재검수에서 `pass` 또는 `warn`인 후보만 UI payload에 전달한다.
- 모든 후보가 실패하면 deterministic fallback 또는 직접 수정 필요 상태를 반환한다.

범위에 포함하지 않는 것:

- 법령 RAG 검색 기반 판단
- 관리자 규칙 편집 UI
- 법적 면책 문구 자동 생성
- 증빙 자료 업로드/검증 자동화

## 아키텍처

```text
CopyComplianceService
  -> PatternMatcher
  -> ComplianceRewritePlanner
  -> ComplianceLLMRewriter
  -> ComplianceCandidateValidator
  -> ComplianceReviewPayloadBuilder
```

### PatternMatcher

기존 규칙 기반 탐지기다. `최고`, `1위`, `100% 보장`, `독소 배출` 같은 표현을 찾고 `ComplianceFinding`을 만든다.

책임:

- 적용 가능한 업종 도메인 규칙 선택
- 필드별 위험 표현 탐지
- `rule_id`, `severity`, `matched_text`, `legal_basis`, `evidence_requirements` 반환

### ComplianceRewritePlanner

탐지된 finding을 보고 어떤 수정 전략이 필요한지 결정한다.

예시 전략:

- `soften_superlative`: 근거 없는 최상급 표현 완화
- `remove_guarantee`: 보장/단정 표현 제거
- `remove_medical_claim`: 식품/화장품 효능 표현 제거
- `request_evidence`: 표현 유지 전 증빙 요구
- `manual_edit_required`: 자동 수정보다 직접 수정이 안전한 경우

Planner는 LLM prompt에 들어갈 구조화된 지시를 만든다.

### ComplianceLLMRewriter

규제 이슈가 있는 경우에만 호출한다.

입력:

- 원문 copy
- 문제가 된 field
- finding 목록
- 업종, 상품/서비스, 광고 목적, 채널
- rewrite strategy
- safe rewrite hints
- 금지 조건

출력:

```json
{
  "candidates": [
    {
      "text": "정성껏 준비한 고기 한 접시",
      "rationale": "최상급 표현을 제거하고 상품 맥락을 유지했습니다."
    }
  ]
}
```

LLM 지침:

- 원문 의미와 상품 맥락을 유지한다.
- 새로운 사실, 수치, 효능, 비교 우위를 만들지 않는다.
- 위험 표현만 안전하게 완화한다.
- 한국어 광고 문구 후보 2~3개를 JSON으로 반환한다.

### ComplianceCandidateValidator

LLM 후보를 다시 `ComplianceService.check_copy()`에 넣어 재검수한다.

통과 기준:

- `pass`: 노출 가능
- `warn`: 노출 가능하되 참고 표시 가능
- `evidence_required`, `blocked`: 후보 제외

모든 후보가 실패하면 1회 재시도한다. 재시도 후에도 후보가 없으면 deterministic fallback을 반환하거나 `manual_edit_required` 상태로 둔다.

### ComplianceReviewPayloadBuilder

UI가 바로 사용할 수 있는 payload를 만든다.

```json
{
  "type": "copy_compliance_review",
  "status": "evidence_required",
  "findings": [
    {
      "matchedText": "최고",
      "reason": "객관적 근거 없는 최상급 표현으로 보일 수 있어요.",
      "suggestions": [
        {
          "text": "정성껏 준비한 고기 한 접시",
          "validationStatus": "pass",
          "rationale": "최상급 표현을 제거하고 상품 맥락을 유지했습니다."
        }
      ]
    }
  ],
  "actions": [
    {
      "id": "use_suggestion",
      "label": "안전한 문구로 수정"
    },
    {
      "id": "edit_manually",
      "label": "직접 수정"
    },
    {
      "id": "submit_evidence",
      "label": "근거가 있어요"
    },
    {
      "id": "cancel",
      "label": "취소"
    }
  ]
}
```

## 데이터 흐름

```text
1. 사용자가 문구 입력
2. ComplianceService.check_copy(copy, business_type) 호출
3. PatternMatcher가 위험 finding 생성
4. finding이 없으면 pass 반환, LLM 호출 없음
5. finding이 있으면 ComplianceRewritePlanner가 rewrite plan 생성
6. ComplianceLLMRewriter가 후보 2~3개 생성
7. ComplianceCandidateValidator가 후보를 재검수
8. 통과 후보만 finding.suggestions와 suggested_copy에 반영
9. UI는 구조화된 review payload를 표시
10. 사용자가 suggestion 선택, 직접 수정, 근거 제출 중 선택
```

## 오류 처리

LLM 호출 실패:

- deterministic fallback rewrite를 사용한다.
- fallback도 실패하면 `manual_edit_required`로 둔다.

LLM JSON 파싱 실패:

- 한 번 JSON repair를 시도한다.
- 실패하면 deterministic fallback으로 전환한다.

후보 재검수 실패:

- 위험 후보는 UI에 노출하지 않는다.
- 모든 후보가 실패하면 한 번 재생성한다.
- 재생성도 실패하면 직접 수정 안내를 표시한다.

LLM이 새로운 사실을 만든 경우:

- 후보 검수 단계에서 제거한다.
- 수치, 보장, 효능, 비교 우위 표현은 별도 guard로 필터링한다.

## 테스트 전략

단위 테스트:

- 규제 이슈가 없으면 LLM 리라이터가 호출되지 않는다.
- `최고다 고기!`는 고기 맥락을 유지한 후보를 만든다.
- 후보 문구에 `최고`가 남아 있으면 제외된다.
- LLM 실패 시 deterministic fallback이 사용된다.
- 모든 후보 실패 시 `manual_edit_required`가 반환된다.

통합 테스트:

- copy compliance gate payload에 `suggestions[]`가 포함된다.
- 사용자가 `use_suggestion`을 선택하면 검수 통과 후보가 다음 copy로 반영된다.
- `edit_manually`는 기존 직접 수정 흐름으로 이동한다.
- `submit_evidence`는 증빙 필요 상태를 유지한다.

회귀 테스트:

- 기존 blocked/warn/evidence_required status 판정은 유지한다.
- 기존 result payload의 `findings`, `publicationReady`, `legalBasis`는 깨지지 않는다.

## 단계별 구현 제안

1. 현재 deterministic rewrite 패치를 유지해 fallback으로 둔다.
2. `ComplianceRewritePlanner`와 schema를 추가한다.
3. `ComplianceLLMRewriter` 인터페이스와 fake/test implementation을 추가한다.
4. LLM 후보 재검수 루프를 추가한다.
5. review payload에 `suggestions[]`를 확장한다.
6. UI가 기존 `suggestedText` 대신 `suggestions[0].text`를 우선 표시하도록 맞춘다.
7. 실제 LLM adapter를 연결하고 env flag로 on/off할 수 있게 한다.

## 결정 사항

- LLM 리라이터는 규제 finding이 있을 때만 호출한다.
- LLM은 법적 판단자가 아니라 문맥형 문구 생성기다.
- 최종 노출 후보는 반드시 규칙 엔진 재검수를 통과해야 한다.
- YAML examples는 사용자 노출용 문구가 아니라 LLM 힌트와 fallback 참고값으로만 사용한다.
