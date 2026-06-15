"use client";

import { Check, PenLine, Send } from "lucide-react";
import { useMemo, useState } from "react";
import type { ComplianceAction, ComplianceFindingFE, ParsedGenerationJobInterrupt } from "@/lib/generation-job-interrupt";
import type { ChatFlowState } from "@/types/marketing";
import { AutosizeTextarea } from "./AutosizeTextarea";
import { ChatTimelineStep } from "./ChatTimelineStep";
import { MascotImage } from "./MascotImage";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type GenerationJobInterruptStepProps = {
  interrupt: ParsedGenerationJobInterrupt;
  state?: ChatFlowState;
  isLoading?: boolean;
  errorMessage?: string | null;
  onBack: () => void;
  onDelete?: () => void;
  onSelectCopyCandidate: (input: { selectedCopyId: string; label: string }) => void;
  onSubmitCustomCopy: (input: { userCustomHeadline: string; userCustomSubcopy?: string; label: string }) => void;
  onComplianceAction?: (action: ComplianceAction) => void;
};

const fallbackCustomFields = [
  {
    field: "user_custom_headline",
    label: "메인 문구",
    placeholder: "광고에 넣을 메인 문구",
    required: true,
    maxRecommendedChars: 15
  },
  {
    field: "user_custom_subcopy",
    label: "보조 문구",
    placeholder: "이벤트 상세나 보조 문구",
    required: false
  }
];

function copyOriginLabel(origin: string): string {
  if (origin === "llm") {
    return "AI 생성";
  }
  if (origin === "rule_based") {
    return "자동 추천";
  }
  if (origin === "fallback") {
    return "안전 추천";
  }
  return "요청 기반";
}

function severityLabel(severity: string | null | undefined): string {
  if (severity === "block") return "게시 차단";
  if (severity === "evidence_required") return "증거 필요";
  if (severity === "warn") return "주의";
  return "확인";
}

function candidateComplianceSeverity(status: string | null | undefined): string {
  return status === "blocked" ? "block" : status || "warn";
}

function candidateComplianceLabel(status: string | null | undefined): string {
  if (status === "blocked" || status === "block") return "게시 차단";
  if (status === "evidence_required") return "근거 필요";
  if (status === "warn") return "주의";
  return "규제 확인";
}

function shouldShowCandidateCompliance(status: string | null | undefined): boolean {
  return Boolean(status && status !== "pass");
}

function ComplianceFinding({ finding }: { finding: ComplianceFindingFE }) {
  const severity = finding.severity ?? "warn";
  const displayReason = finding.hitl_question ?? finding.reason;
  return (
    <div className={styles.complianceFindingCard} data-severity={severity}>
      <div className={styles.complianceFindingHeader}>
        <span className={styles.severityBadge} data-severity={severity}>
          {severityLabel(severity)}
        </span>
        {finding.field && <span className={styles.complianceFieldLabel}>{finding.field}</span>}
      </div>
      {finding.matched_text && (
        <p className={styles.complianceMatchedText}>&ldquo;{finding.matched_text}&rdquo;</p>
      )}
      {displayReason && <p className={styles.complianceReason}>{displayReason}</p>}
      {finding.suggested_text && (
        <div className={styles.complianceSuggestion}>
          <span className={styles.complianceSuggestionLabel}>제안</span>
          <span>{finding.suggested_text}</span>
        </div>
      )}
      {finding.legal_basis && finding.legal_basis.length > 0 && (
        <ul className={styles.complianceLegalBasis}>
          {finding.legal_basis.map((b, i) => (
            <li key={i}>
              {b.law_name}
              {b.article ? ` ${b.article}` : ""}
              {b.summary ? ` — ${b.summary}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function GenerationJobInterruptStep({
  interrupt,
  state,
  isLoading = false,
  errorMessage,
  onBack,
  onDelete,
  onSelectCopyCandidate,
  onSubmitCustomCopy,
  onComplianceAction
}: GenerationJobInterruptStepProps) {
  const [headline, setHeadline] = useState("");
  const [subcopy, setSubcopy] = useState("");
  // Local selection: nothing pre-selected so the AI recommendation is shown as a
  // badge only, never as an already-checked card. Submission happens on "선택 완료".
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const fields = useMemo(
    () => (interrupt.type === "custom_copy_input" && interrupt.fields.length > 0 ? interrupt.fields : fallbackCustomFields),
    [interrupt]
  );
  const shouldShowCustomCopyEditor =
    interrupt.type === "custom_copy_input" || (interrupt.type === "copy_candidate_selection" && selectedOptionId === "custom");

  function submitCustomCopy() {
    const nextHeadline = headline.trim();
    const nextSubcopy = subcopy.trim();
    if (isLoading || !nextHeadline) {
      return;
    }
    onSubmitCustomCopy({
      userCustomHeadline: nextHeadline,
      userCustomSubcopy: nextSubcopy || undefined,
      label: nextSubcopy ? `${nextHeadline} / ${nextSubcopy}` : nextHeadline
    });
  }

  function submitSelection() {
    if (isLoading || !selectedOptionId || interrupt.type !== "copy_candidate_selection") {
      return;
    }
    if (selectedOptionId === "custom") {
      submitCustomCopy();
      return;
    }
    const selected = interrupt.candidates.find((candidate) => candidate.id === selectedOptionId);
    if (!selected) {
      return;
    }
    onSelectCopyCandidate({ selectedCopyId: selected.id, label: selected.headline });
  }

  const content = (
    <>
      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>
          {interrupt.type === "copy_candidate_selection"
            ? "이미지에 반영할 문구를 골라주세요."
            : interrupt.type === "custom_copy_input"
              ? "직접 넣을 문구를 확인하면 같은 생성 요청을 이어갈게요."
              : interrupt.type === "copy_compliance_review"
                ? "광고 문구에서 규제 관련 표현이 발견되었어요. 아래 내용을 확인하고 진행 방법을 선택해주세요."
                : "생성을 이어가기 위해 확인이 필요한 정보가 있어요."}
        </p>
      </div>

      {interrupt.type === "copy_candidate_selection" ? (
        <>
          <h2 className={styles.sectionTitle}>사용할 문구를 골라주세요</h2>
          <p className={styles.helperText}>
            {copyOriginLabel(interrupt.copyCandidateOrigin)} 문구 후보예요. 선택하면 같은 생성 요청이 이어집니다.
          </p>
          <div className={styles.selectList}>
            {interrupt.candidates.map((candidate, index) => {
              const recommended = candidate.id === interrupt.recommendedCandidateId;
              const copyDetail = [candidate.subcopy, candidate.cta].filter(Boolean).join(" · ");
              const compliance = candidate.metadata?.compliance ?? null;
              const complianceStatus = compliance?.status ?? null;
              const complianceDisabled = Boolean(compliance?.disabled);
              const findingCount = typeof compliance?.finding_count === "number" ? compliance.finding_count : null;
              return (
                <button
                  key={candidate.id}
                  type="button"
                  className={`${styles.copyCard} ${selectedOptionId === candidate.id ? styles.copyCardSelected : ""}`}
                  aria-label={`${candidate.headline} 선택`}
                  aria-pressed={selectedOptionId === candidate.id}
                  disabled={isLoading || complianceDisabled}
                  onClick={() => setSelectedOptionId(candidate.id)}
                >
                  <span className={styles.copyNumber}>{index + 1}</span>
                  <span className={styles.copyContent}>
                    <span>
                      {candidate.headline}
                      {recommended ? <small> · AI 추천</small> : null}
                    </span>
                    {copyDetail ? <small>{copyDetail}</small> : null}
                    {shouldShowCandidateCompliance(complianceStatus) ? (
                      <span className={styles.candidateComplianceLine}>
                        <span
                          className={styles.severityBadge}
                          data-severity={candidateComplianceSeverity(complianceStatus)}
                        >
                          {candidateComplianceLabel(complianceStatus)}
                        </span>
                        {findingCount ? <small>규제 표현 {findingCount}건</small> : null}
                      </span>
                    ) : null}
                  </span>
                  {selectedOptionId === candidate.id ? <Check size={19} aria-hidden="true" /> : <span />}
                </button>
              );
            })}
            <button
              key="custom"
              type="button"
              className={`${styles.copyCard} ${styles.copyCandidateManualButton} ${selectedOptionId === "custom" ? styles.copyCardSelected : ""}`}
              aria-label="직접 문구 입력 선택"
              aria-pressed={selectedOptionId === "custom"}
              disabled={isLoading}
              onClick={() => setSelectedOptionId("custom")}
            >
              <span className={styles.copyNumber}>
                <PenLine size={17} aria-hidden="true" />
              </span>
              <span className={styles.copyContent}>
                <span>직접 문구 입력</span>
                <small>원하는 문구를 직접 작성</small>
              </span>
              {selectedOptionId === "custom" ? <Check size={19} aria-hidden="true" /> : <span />}
            </button>
          </div>
        </>
      ) : null}

      {shouldShowCustomCopyEditor ? (
        <>
          <h2 className={styles.sectionTitle}>
            {interrupt.type === "custom_copy_input" ? "광고 문구를 입력해주세요" : "직접 사용할 문구를 입력해주세요"}
          </h2>
          <div className={styles.customCopyFields}>
            {fields.map((field) => {
              const isHeadline = field.field === "user_custom_headline" || field.field === "headline";
              return (
                <label className={styles.customCopyField} key={field.field}>
                  <span>
                    {field.label}
                    {field.required ? " · 필수" : ""}
                    {field.maxRecommendedChars ? ` · ${field.maxRecommendedChars}자 권장` : ""}
                  </span>
                  <AutosizeTextarea
                    className={styles.customCopyTextarea}
                    value={isHeadline ? headline : subcopy}
                    aria-label={isHeadline ? "생성 재개 메인 문구 입력" : "생성 재개 보조 문구 입력"}
                    placeholder={field.placeholder}
                    disabled={isLoading}
                    onChange={(event) => (isHeadline ? setHeadline(event.target.value) : setSubcopy(event.target.value))}
                    onSubmit={submitCustomCopy}
                  />
                </label>
              );
            })}
          </div>
          {interrupt.type === "custom_copy_input" ? (
            <button
              className={styles.primaryButton}
              type="button"
              disabled={isLoading || !headline.trim()}
              onClick={submitCustomCopy}
            >
              <Send size={18} aria-hidden="true" />
              문구로 생성 이어가기
            </button>
          ) : null}
        </>
      ) : null}

      {interrupt.type === "copy_candidate_selection" ? (
        <button
          className={styles.primaryButton}
          type="button"
          disabled={isLoading || !selectedOptionId || (selectedOptionId === "custom" && !headline.trim())}
          onClick={submitSelection}
        >
          <Send size={18} aria-hidden="true" />
          선택 완료
        </button>
      ) : null}

      {interrupt.type === "copy_compliance_review" ? (
        <>
          <h2 className={styles.sectionTitle}>광고 규제 검토 결과</h2>
          <p className={styles.helperText}>{interrupt.summary}</p>
          {interrupt.findings.length > 0 && (
            <div className={styles.complianceFindingList}>
              {interrupt.findings.map((finding, index) => (
                <ComplianceFinding key={finding.finding_id ?? index} finding={finding} />
              ))}
            </div>
          )}
          <div className={styles.complianceActionRow}>
            {interrupt.actions
              .filter((action) => action.available)
              .map((action) => (
                <button
                  key={action.id}
                  type="button"
                  className={action.id === "use_suggestion" ? styles.primaryButton : styles.secondaryButton}
                  data-danger={action.id === "cancel" ? "true" : undefined}
                  disabled={
                    isLoading ||
                    (action.id === "keep_original_draft" && interrupt.status === "block")
                  }
                  onClick={() => onComplianceAction?.(action)}
                >
                  {action.label}
                </button>
              ))}
          </div>
        </>
      ) : null}

      {interrupt.type === "unsupported" ? (
        <section className={styles.emptyResultPanel} aria-label="지원하지 않는 추가 선택">
          <MascotImage role="questionPaper" decorative className={styles.emptyMascot} />
          <strong>이 선택은 아직 화면에서 처리할 수 없어요</strong>
          <p>생성 요청을 다시 보내거나 잠시 후 다시 시도해주세요.</p>
        </section>
      ) : null}

      {errorMessage ? <p className={styles.helperText}>{errorMessage}</p> : null}

      {interrupt.type === "copy_candidate_selection" ? (
        <p className={styles.helperText}>
          <PenLine size={14} aria-hidden="true" /> 선택한 문구가 이미지에 반영되고, 같은 생성 요청이 이어집니다.
        </p>
      ) : null}
    </>
  );

  if (state) {
    return (
      <ChatTimelineStep state={state} onBack={onBack} onDelete={onDelete}>
        {content}
      </ChatTimelineStep>
    );
  }

  return (
    <>
      <StepHeader title="생성에 필요한 선택을 마저 해주세요" canGoBack onBack={onBack} />
      {content}
    </>
  );
}
