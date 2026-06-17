import type { CopyCandidateOrigin } from "@/types/marketing";

export function copyCandidateOriginLabel(origin: CopyCandidateOrigin, fallbackUsed = false): string {
  if (origin === "mock") {
    return "테스트 추천 문구";
  }
  if (fallbackUsed || origin === "fallback") {
    return "임시 추천 문구";
  }
  if (origin === "llm") {
    return "AI 추천 문구";
  }
  if (origin === "rule_based") {
    return "기본 추천 문구";
  }
  return "추천 문구";
}

export function copyCandidateOriginNote(origin: CopyCandidateOrigin, fallbackUsed = false): string {
  if (origin === "mock") {
    return "테스트 환경에서 준비된 추천 문구입니다.";
  }
  if (fallbackUsed || origin === "fallback") {
    return "AI 문구 생성이 완료되지 않아 기본 추천 문구를 표시했습니다.";
  }
  if (origin === "llm") {
    return "AI가 이번 요청을 바탕으로 만든 문구 후보예요. 선택한 문구가 이미지에 반영됩니다.";
  }
  if (origin === "rule_based") {
    return "요청 정보를 바탕으로 어울리는 추천 문구를 준비했어요. 선택한 문구가 이미지에 반영됩니다.";
  }
  return "이번 요청을 바탕으로 준비된 문구 후보예요. 선택한 문구가 이미지에 반영됩니다.";
}
