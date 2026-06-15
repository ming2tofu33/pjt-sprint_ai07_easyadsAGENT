import { describe, expect, it } from "vitest";

import fixtures from "@/types/contracts/generation-job-interrupt.fixtures.json";
import { parseGenerationJobInterrupt } from "./generation-job-interrupt";

describe("generation job interrupt contract", () => {
  it("parses backend option-question fixture", () => {
    const parsed = parseGenerationJobInterrupt(fixtures.optionQuestion);

    expect(parsed?.type).toBe("option_question");
    expect(parsed?.type === "option_question" ? parsed.optionQuestion.field : null).toBe("business_type");
    expect(parsed?.type === "option_question" ? parsed.optionQuestion.options.length : 0).toBe(2);
  });

  it("parses backend copy-candidate selection fixture", () => {
    const parsed = parseGenerationJobInterrupt(fixtures.copyCandidateSelection);

    expect(parsed?.type).toBe("copy_candidate_selection");
    expect(parsed?.type === "copy_candidate_selection" ? parsed.recommendedCandidateId : null).toBe("copy_1");
    expect(parsed?.type === "copy_candidate_selection" ? parsed.candidates[0]?.headline : null).toBe("오늘 한 잔, 시원하게");
  });

  it("parses backend custom-copy input fixture", () => {
    const parsed = parseGenerationJobInterrupt(fixtures.customCopyInput);

    expect(parsed?.type).toBe("custom_copy_input");
    expect(parsed?.type === "custom_copy_input" ? parsed.fields[0]?.field : null).toBe("user_custom_headline");
  });

  it("parses backend copy-compliance review fixture", () => {
    const parsed = parseGenerationJobInterrupt(fixtures.copyComplianceReview);

    expect(parsed?.type).toBe("copy_compliance_review");
    expect(parsed?.type === "copy_compliance_review" ? parsed.status : null).toBe("evidence_required");
    expect(parsed?.type === "copy_compliance_review" ? parsed.actions[0]?.id : null).toBe("use_suggestion");
  });

  it("parses compliance rewrite suggestions", () => {
    const parsed = parseGenerationJobInterrupt(fixtures.copyComplianceReview);

    expect(parsed?.type).toBe("copy_compliance_review");
    if (parsed?.type !== "copy_compliance_review") return;
    expect(parsed.findings[0]?.suggestions?.[0]?.text).toBe("정성껏 준비한 고기 한 접시");
  });
});
