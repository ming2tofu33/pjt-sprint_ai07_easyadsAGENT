import { describe, expect, it } from "vitest";

import { copyCandidateOriginLabel, copyCandidateOriginNote } from "./CopyChannelStep";

describe("CopyChannelStep copy source labels", () => {
  it.each([
    ["llm", false, "AI 추천 문구"],
    ["rule_based", false, "기본 추천 문구"],
    ["fallback", false, "임시 추천 문구"],
    ["mock", false, "테스트 추천 문구"],
    ["unknown", false, "추천 문구"],
    ["llm", true, "임시 추천 문구"],
  ] as const)("maps origin=%s fallback=%s to %s", (origin, fallbackUsed, expected) => {
    expect(copyCandidateOriginLabel(origin, fallbackUsed)).toBe(expected);
  });

  it("does not show the AI label for fallback copy", () => {
    expect(copyCandidateOriginLabel("fallback")).not.toBe("AI 추천 문구");
    expect(copyCandidateOriginLabel("llm", true)).not.toBe("AI 추천 문구");
  });

  it("shows a safe generic fallback note without provider errors", () => {
    expect(copyCandidateOriginNote("fallback")).toBe("AI 문구 생성이 완료되지 않아 기본 추천 문구를 표시했습니다.");
  });
});
