export type UiGraphCapability =
  | "chat.start"
  | "chat.answer-context-question"
  | "generation-job.answer-context-question"
  | "copy-mode.suggest-candidates"
  | "copy-selection.copy-channel-tone"
  | "copy-selection.visual-direction"
  | "photo.upload-source-image"
  | "photo.start"
  | "copy-mode.auto-pilot"
  | "copy-mode.custom-input"
  | "copy.custom-headline-input"
  | "copy-mode.no-copy"
  | "reference.template-selection"
  | "photo.final-source-image"
  | "reference.direct-image-upload"
  | "generation.copy-candidate-selection-interrupt"
  | "generation.custom-copy-input-interrupt"
  | "generation.selected-copy-state"
  | "generation.selected-channel-state"
  | "generation.selected-tone-state"
  | "validation.feedback-visible"
  | "thread.state-restore"
  | "result.quality-feedback"
  | "generation.progress-visible";

export type UiGraphCoveragePhase =
  | "initial-generation"
  | "final-graph-integration-v1"
  | "result-feedback";

export type UiGraphCoverageExpectation = {
  id: string;
  label: string;
  userFlow: string;
  phase: UiGraphCoveragePhase;
  requiredCapabilities: UiGraphCapability[];
  expectedGraphNodes: string[];
};

export type UiGraphCoverageItem = UiGraphCoverageExpectation & {
  covered: boolean;
  missingCapabilities: UiGraphCapability[];
};

export type UiGraphCoverageReport = {
  items: UiGraphCoverageItem[];
  coveredIds: string[];
  uncoveredIds: string[];
  coveredCount: number;
  totalCount: number;
  coverageRatio: number;
};

export const CURRENT_UI_GRAPH_CAPABILITIES: UiGraphCapability[] = [
  "chat.start",
  "chat.answer-context-question",
  "generation-job.answer-context-question",
  "copy-mode.suggest-candidates",
  "copy-selection.copy-channel-tone",
  "copy-selection.visual-direction",
  "photo.upload-source-image",
  "photo.start",
  "copy-mode.auto-pilot",
  "copy-mode.no-copy",
  "copy-mode.custom-input",
  "copy.custom-headline-input",
  "reference.template-selection",
  "photo.final-source-image",
  "reference.direct-image-upload",
  "generation.copy-candidate-selection-interrupt",
  "generation.custom-copy-input-interrupt",
  "generation.selected-copy-state",
  "generation.selected-channel-state",
  "generation.selected-tone-state",
  "validation.feedback-visible",
  "thread.state-restore",
  "result.quality-feedback",
  "generation.progress-visible",
];

export const UI_GRAPH_COVERAGE_MATRIX: UiGraphCoverageExpectation[] = [
  {
    id: "missing-context-loop",
    label: "부족 컨텍스트 질문 루프",
    userFlow: "대화 시작 후 부족한 업종/상품/목적 질문에 답변",
    phase: "initial-generation",
    requiredCapabilities: ["chat.start", "chat.answer-context-question"],
    expectedGraphNodes: ["validator", "options", "state_update"],
  },
  {
    id: "generation-job-context-loop",
    label: "최종 생성 중 부족 컨텍스트 질문 재개",
    userFlow: "브리프 확인 후 최종 생성 job이 추가 질문을 요청하면 답변하고 같은 job을 재개",
    phase: "final-graph-integration-v1",
    requiredCapabilities: ["chat.start", "generation-job.answer-context-question"],
    expectedGraphNodes: ["validator", "options", "state_update", "t2i_request_builder"],
  },
  {
    id: "chat-suggest-candidates",
    label: "대화 기반 추천 문구 선택",
    userFlow: "대화로 시작해서 추천 문구를 선택하고 브리프 생성",
    phase: "initial-generation",
    requiredCapabilities: ["chat.start", "copy-mode.suggest-candidates", "copy-selection.copy-channel-tone"],
    expectedGraphNodes: ["copy_candidate_generation", "copy_candidate_selection_interrupt", "state_update_selected_copy"],
  },
  {
    id: "photo-source-suggest-candidates",
    label: "사진 업로드 기반 생성",
    userFlow: "사진 업로드 후 추천 문구를 선택하고 이미지 생성",
    phase: "initial-generation",
    requiredCapabilities: ["photo.upload-source-image", "photo.start", "copy-mode.suggest-candidates", "copy-selection.copy-channel-tone"],
    expectedGraphNodes: ["product_preprocess", "copy_candidate_generation", "t2i_request_builder", "t2i_generation"],
  },
  {
    id: "photo-final-source-image",
    label: "최종 생성 사진 원본 반영",
    userFlow: "사진 업로드로 시작한 요청의 source image를 최종 generation job graph state까지 전달",
    phase: "final-graph-integration-v1",
    requiredCapabilities: ["photo.final-source-image"],
    expectedGraphNodes: ["product_preprocess", "t2i_request_builder", "t2i_generation"],
  },
  {
    id: "custom-visual-direction",
    label: "사용자 이미지 방향 반영",
    userFlow: "문구/채널 화면에서 원하는 이미지 방향을 직접 입력",
    phase: "initial-generation",
    requiredCapabilities: ["copy-selection.visual-direction"],
    expectedGraphNodes: ["image_prompt_planner", "prompt_renderer"],
  },
  {
    id: "auto-pilot-copywriting",
    label: "AI 자동 문구 완성",
    userFlow: "문구 후보 선택 없이 AI가 최적 문구 하나를 자동 적용",
    phase: "initial-generation",
    requiredCapabilities: ["copy-mode.auto-pilot"],
    expectedGraphNodes: ["auto_pilot_copywriting", "copy_spec_parser"],
  },
  {
    id: "custom-copy-input",
    label: "사용자 직접 문구 입력",
    userFlow: "광고에 들어갈 headline/subcopy를 사용자가 직접 입력",
    phase: "initial-generation",
    requiredCapabilities: ["copy-mode.custom-input", "copy.custom-headline-input"],
    expectedGraphNodes: ["custom_copy_input", "custom_copy_validation", "copy_spec_parser"],
  },
  {
    id: "generation-selected-ui-state",
    label: "선택 문구/채널/톤 최종 state 반영",
    userFlow: "UI에서 고른 문구, 채널, 톤을 최종 generation job graph state로 전달",
    phase: "final-graph-integration-v1",
    requiredCapabilities: [
      "generation.selected-copy-state",
      "generation.selected-channel-state",
      "generation.selected-tone-state",
    ],
    expectedGraphNodes: ["state_update_selected_copy", "format_planner", "tone_binding"],
  },
  {
    id: "generation-copy-candidate-interrupt",
    label: "최종 생성 문구 후보 선택 interrupt",
    userFlow: "최종 generation job이 문구 후보 선택을 요청하면 UI에서 선택 후 같은 job을 재개",
    phase: "final-graph-integration-v1",
    requiredCapabilities: ["generation.copy-candidate-selection-interrupt"],
    expectedGraphNodes: ["copy_candidate_selection_interrupt", "state_update_selected_copy"],
  },
  {
    id: "generation-custom-copy-interrupt",
    label: "최종 생성 직접 문구 입력 interrupt",
    userFlow: "최종 generation job이 직접 문구 입력을 요청하면 UI에서 headline/subcopy를 입력 후 같은 job을 재개",
    phase: "final-graph-integration-v1",
    requiredCapabilities: ["generation.custom-copy-input-interrupt"],
    expectedGraphNodes: ["custom_copy_input", "custom_copy_validation", "copy_spec_parser"],
  },
  {
    id: "no-copy-image-only",
    label: "문구 없는 이미지 생성",
    userFlow: "텍스트 없이 이미지만 생성",
    phase: "initial-generation",
    requiredCapabilities: ["copy-mode.no-copy"],
    expectedGraphNodes: ["no_copy_bypass", "safe_area_gate", "result"],
  },
  {
    id: "reference-template",
    label: "샘플 템플릿 기반 생성",
    userFlow: "샘플 갤러리에서 템플릿을 선택해 스타일을 반영",
    phase: "initial-generation",
    requiredCapabilities: ["reference.template-selection"],
    expectedGraphNodes: ["reference_template_resolve", "image_prompt_planner"],
  },
  {
    id: "reference-image",
    label: "샘플 이미지 기반 생성",
    userFlow: "스타일 참조 이미지를 업로드해 분위기를 반영",
    phase: "final-graph-integration-v1",
    requiredCapabilities: ["reference.direct-image-upload"],
    expectedGraphNodes: ["reference_preprocess", "image_prompt_planner"],
  },
  {
    id: "validation-feedback",
    label: "검증 결과 UI 피드백",
    userFlow: "safe area/readability/final validation 결과를 사용자에게 표시",
    phase: "result-feedback",
    requiredCapabilities: ["validation.feedback-visible"],
    expectedGraphNodes: ["background_validation", "safe_area_gate", "readability_gate", "final_validation"],
  },
  {
    id: "thread-state-restore",
    label: "작업방 상태 복원",
    userFlow: "최근 작업방에서 보기를 누르면 이전 대화, 선택 문구, 생성 결과 상태를 복원",
    phase: "result-feedback",
    requiredCapabilities: ["thread.state-restore"],
    expectedGraphNodes: ["validator", "copy_candidate_generation", "t2i_generation", "result"],
  },
  {
    id: "result-quality-feedback",
    label: "결과 품질/검수 상태 표시",
    userFlow: "최종 결과 화면에서 OCR, 검수, 수동 확인 필요 여부를 표시",
    phase: "result-feedback",
    requiredCapabilities: ["result.quality-feedback", "validation.feedback-visible"],
    expectedGraphNodes: ["background_ocr_gate", "final_ocr_gate", "readability_gate", "final_validation", "result"],
  },
];

export function buildUiGraphCoverageReport(
  capabilities: UiGraphCapability[] = CURRENT_UI_GRAPH_CAPABILITIES,
  matrix: UiGraphCoverageExpectation[] = UI_GRAPH_COVERAGE_MATRIX
): UiGraphCoverageReport {
  const capabilitySet = new Set(capabilities);
  const items = matrix.map((item) => {
    const missingCapabilities = item.requiredCapabilities.filter((capability) => !capabilitySet.has(capability));
    return {
      ...item,
      covered: missingCapabilities.length === 0,
      missingCapabilities,
    };
  });
  const coveredIds = items.filter((item) => item.covered).map((item) => item.id);
  const uncoveredIds = items.filter((item) => !item.covered).map((item) => item.id);
  const totalCount = items.length;
  const coveredCount = coveredIds.length;

  return {
    items,
    coveredIds,
    uncoveredIds,
    coveredCount,
    totalCount,
    coverageRatio: totalCount > 0 ? coveredCount / totalCount : 1,
  };
}

export function findUiGraphCoverageItem(report: UiGraphCoverageReport, id: string): UiGraphCoverageItem | undefined {
  return report.items.find((item) => item.id === id);
}
