export type UiOrchestratorExecutionMode =
  | "langgraph-interrupt-loop"
  | "langgraph-resume"
  | "generation-job-direct-t2i"
  | "generation-job-graph"
  | "ui-only";

export type UiOrchestratorCoveragePhase =
  | "initial-context"
  | "final-graph-integration-v1"
  | "result-feedback";

export type UiOrchestratorRouteCoverageRow = {
  id: string;
  label: string;
  userFlow: string;
  phase: UiOrchestratorCoveragePhase;
  uiEntryPoints: string[];
  apiCalls: string[];
  executionMode: UiOrchestratorExecutionMode;
  connected: boolean;
  fullGraphExecution: boolean;
  graphStateFields: string[];
  graphNodesReached: string[];
  graphNodesBypassed: string[];
  testEvidence: string[];
  notes: string;
};

export type UiOrchestratorRouteCoverageReport = {
  rows: UiOrchestratorRouteCoverageRow[];
  connectedIds: string[];
  disconnectedIds: string[];
  fullGraphIds: string[];
  directT2iIds: string[];
  connectedCount: number;
  totalCount: number;
  fullGraphCount: number;
};

const FINAL_GENERATION_GRAPH_CHAIN = [
  "format_planner",
  "tone_binding",
  "copy_spec_parser",
  "text_style_binder",
  "text_layout_planner",
  "image_prompt_planner",
  "prompt_renderer",
  "t2i_request_builder",
  "t2i_generation",
  "background_validation",
  "safe_area_gate",
  "text_renderer",
  "readability_gate",
  "final_validation",
  "result"
];

export const UI_ORCHESTRATOR_ROUTE_COVERAGE: UiOrchestratorRouteCoverageRow[] = [
  {
    id: "context-question-loop",
    label: "부족 컨텍스트 질문 루프",
    userFlow: "정보가 부족한 대화 입력 후 AI 질문에 답변",
    phase: "initial-context",
    uiEntryPoints: ["ChatStartStep", "ChatContextQuestionStep"],
    apiCalls: ["POST /api/generate/chat/start", "POST /api/generate/chat/answer"],
    executionMode: "langgraph-interrupt-loop",
    connected: true,
    fullGraphExecution: false,
    graphStateFields: ["thread_id", "context"],
    graphNodesReached: ["input", "validator", "options", "state_update"],
    graphNodesBypassed: FINAL_GENERATION_GRAPH_CHAIN,
    testEvidence: ["apps/web/app/generate/chat/ChatGenerateClient.test.tsx"],
    notes: "초기 컨텍스트 수집 루프는 LangGraph interrupt/resume로 연결되어 있지만, 최종 이미지 생성 체인까지 실행하는 단계는 아니다."
  },
  {
    id: "brief-confirmation",
    label: "브리프 확인",
    userFlow: "문구/채널/톤 선택 후 브리프 확인",
    phase: "initial-context",
    uiEntryPoints: ["CopyChannelStep", "BriefConfirmStep"],
    apiCalls: ["POST /api/generate/chat/brief"],
    executionMode: "langgraph-resume",
    connected: true,
    fullGraphExecution: false,
    graphStateFields: ["selected_copy_id", "selected_channel_id", "selected_tone"],
    graphNodesReached: ["copy_candidate_selection_interrupt", "state_update_selected_copy", "copy_spec_parser"],
    graphNodesBypassed: ["t2i_generation", "background_validation", "safe_area_gate", "text_renderer", "readability_gate", "final_validation", "result"],
    testEvidence: ["apps/web/app/generate/chat/ChatGenerateClient.test.tsx"],
    notes: "사용자 선택값은 graph resume으로 들어가지만, UI는 이 단계에서 실제 이미지 생성/검증 결과를 받지 않는다."
  },
  {
    id: "final-model-generation",
    label: "모델 선택 최종 이미지 생성",
    userFlow: "GPT-image-2, FLUX.1-schnell, SD3.5 Large 중 하나를 선택해 최종 생성",
    phase: "final-graph-integration-v1",
    uiEntryPoints: ["GenerationEngineSelector", "BriefConfirmStep", "GenerationInProgressStep", "GenerationCompleteStep"],
    apiCalls: ["POST /api/generation-jobs", "GET /api/generation-jobs/{job_id}"],
    executionMode: "generation-job-graph",
    connected: true,
    fullGraphExecution: true,
    graphStateFields: ["image_generation_engine", "requested_engine", "t2i_engine"],
    graphNodesReached: FINAL_GENERATION_GRAPH_CHAIN,
    graphNodesBypassed: [],
    testEvidence: ["apps/web/app/generate/chat/ChatGenerateClient.test.tsx", "orchestrator/tests/test_generation_job_graph_execution.py"],
    notes: "현재 UI의 모델 선택은 graph_job generation job으로 전달되며, 선택 엔진은 graph state의 engine preference로 t2i_generation 노드까지 전달된다."
  },
  {
    id: "reference-template-selection",
    label: "샘플 템플릿 선택",
    userFlow: "샘플 갤러리에서 템플릿을 선택해 다음 생성 요청에 전달",
    phase: "initial-context",
    uiEntryPoints: ["ReferenceBrowseStep", "ChatStartStep"],
    apiCalls: ["GET /api/references", "POST /api/generate/chat/start", "POST /api/generation-jobs"],
    executionMode: "langgraph-interrupt-loop",
    connected: true,
    fullGraphExecution: false,
    graphStateFields: ["selected_reference_template_id"],
    graphNodesReached: ["reference_template_resolve", "validator", "image_prompt_planner"],
    graphNodesBypassed: ["background_validation", "safe_area_gate", "readability_gate", "final_validation"],
    testEvidence: ["apps/web/app/generate/chat/ChatGenerateClient.test.tsx", "orchestrator/tests/test_generation_jobs_api.py"],
    notes: "템플릿 id는 graph 시작과 final graph generation job에 전달되며, 최종 이미지 생성의 style hint로 이어진다."
  },
  {
    id: "photo-final-source-image",
    label: "최종 생성 사진 원본 반영",
    userFlow: "사진 업로드로 시작한 요청의 source image를 최종 generation job graph state까지 전달",
    phase: "final-graph-integration-v1",
    uiEntryPoints: ["PhotoGenerateStep", "ChatGenerateClient"],
    apiCalls: ["POST /api/generation-jobs"],
    executionMode: "generation-job-graph",
    connected: true,
    fullGraphExecution: false,
    graphStateFields: ["source_image_path"],
    graphNodesReached: ["product_preprocess", "t2i_request_builder", "t2i_generation"],
    graphNodesBypassed: [],
    testEvidence: [
      "apps/web/app/generate/chat/ChatGenerateClient.test.tsx",
      "orchestrator/tests/test_generation_job_graph_execution.py"
    ],
    notes: "photo start에서 업로드한 sourceImagePath가 최종 generation job payload와 graph state의 source_image_path로 보존된다."
  },
  {
    id: "generation-selected-ui-state",
    label: "선택 문구/채널/톤 최종 state 반영",
    userFlow: "UI에서 고른 문구, 채널, 톤을 최종 generation job graph state로 전달",
    phase: "final-graph-integration-v1",
    uiEntryPoints: ["CopyChannelStep", "BriefConfirmStep"],
    apiCalls: ["POST /api/generation-jobs"],
    executionMode: "generation-job-graph",
    connected: true,
    fullGraphExecution: false,
    graphStateFields: ["selected_copy_id", "selected_channel_id", "selected_tone"],
    graphNodesReached: ["state_update_selected_copy", "format_planner", "tone_binding"],
    graphNodesBypassed: [],
    testEvidence: [
      "apps/web/app/generate/chat/ChatGenerateClient.test.tsx",
      "apps/bff/tests/generate.test.js",
      "orchestrator/tests/test_generation_job_graph_execution.py"
    ],
    notes: "선택 문구, 채널, 톤과 직접 방향/문구 입력값이 generation job payload의 first-class graph state 필드로 전달된다."
  },
  {
    id: "generation-copy-candidate-interrupt",
    label: "최종 생성 문구 후보 선택 interrupt",
    userFlow: "최종 generation job이 문구 후보 선택을 요청하면 UI에서 선택 후 같은 job을 재개",
    phase: "final-graph-integration-v1",
    uiEntryPoints: ["GenerationJobInterruptStep", "ChatGenerateClient"],
    apiCalls: ["POST /api/generation-jobs/{job_id}/answer"],
    executionMode: "generation-job-graph",
    connected: true,
    fullGraphExecution: false,
    graphStateFields: ["selected_copy_id"],
    graphNodesReached: ["copy_candidate_selection_interrupt", "state_update_selected_copy"],
    graphNodesBypassed: [],
    testEvidence: [
      "apps/web/lib/generation-job-interrupt.test.ts",
      "apps/web/app/generate/chat/ChatGenerateClient.test.tsx"
    ],
    notes: "graph interrupt type copy_candidate_selection을 파싱하고 선택한 candidate id를 같은 generation job resume payload로 보낸다."
  },
  {
    id: "generation-custom-copy-interrupt",
    label: "최종 생성 직접 문구 입력 interrupt",
    userFlow: "최종 generation job이 직접 문구 입력을 요청하면 UI에서 headline/subcopy를 입력 후 같은 job을 재개",
    phase: "final-graph-integration-v1",
    uiEntryPoints: ["GenerationJobInterruptStep", "ChatGenerateClient"],
    apiCalls: ["POST /api/generation-jobs/{job_id}/answer"],
    executionMode: "generation-job-graph",
    connected: true,
    fullGraphExecution: false,
    graphStateFields: ["user_custom_headline", "user_custom_subcopy"],
    graphNodesReached: ["custom_copy_input", "custom_copy_validation", "copy_spec_parser"],
    graphNodesBypassed: [],
    testEvidence: [
      "apps/web/lib/generation-job-interrupt.test.ts",
      "apps/web/app/generate/chat/ChatGenerateClient.test.tsx"
    ],
    notes: "graph interrupt type custom_copy_input을 파싱하고 headline/subcopy를 같은 generation job resume payload로 보낸다."
  },
  {
    id: "reference.direct-image-upload",
    label: "샘플 이미지 업로드",
    userFlow: "사용자가 스타일 참조 이미지를 직접 업로드",
    phase: "final-graph-integration-v1",
    uiEntryPoints: ["ChatStartStep", "ChatGenerateClient"],
    apiCalls: ["POST /api/generate/photo/upload", "POST /api/generate/chat/start", "POST /api/generation-jobs"],
    executionMode: "generation-job-graph",
    connected: true,
    fullGraphExecution: false,
    graphStateFields: ["reference_image_path"],
    graphNodesReached: ["reference_preprocess", "image_prompt_planner"],
    graphNodesBypassed: [],
    testEvidence: [
      "apps/web/app/generate/chat/ChatGenerateClient.test.tsx",
      "apps/bff/tests/generate.test.js",
      "orchestrator/tests/test_chat_api.py",
      "orchestrator/tests/test_generation_job_graph_execution.py"
    ],
    notes: "대화 시작 화면에서 직접 업로드한 참고 이미지를 referenceImagePath로 저장하고 최종 graph state의 reference_image_path까지 보존한다."
  },
  {
    id: "validation-feedback",
    label: "검증 결과 피드백",
    userFlow: "생성 후 safe area/readability/final validation 결과 확인",
    phase: "result-feedback",
    uiEntryPoints: ["GenerationCompleteStep", "ValidationSummaryPanel"],
    apiCalls: ["GET /api/generation-jobs/{job_id}"],
    executionMode: "ui-only",
    connected: true,
    fullGraphExecution: false,
    graphStateFields: ["validation_summary"],
    graphNodesReached: ["background_validation", "safe_area_gate", "readability_gate", "final_validation"],
    graphNodesBypassed: [],
    testEvidence: [
      "apps/web/lib/generation-result-utils.test.ts",
      "apps/web/app/generate/chat/ChatGenerateClient.test.tsx"
    ],
    notes: "generation job result_payload.validation_summary를 사용자 친화적인 검수 패널로 표시한다."
  }
];

export function buildUiOrchestratorRouteCoverageReport(
  rows: UiOrchestratorRouteCoverageRow[] = UI_ORCHESTRATOR_ROUTE_COVERAGE
): UiOrchestratorRouteCoverageReport {
  const connectedIds = rows.filter((row) => row.connected).map((row) => row.id);
  const disconnectedIds = rows.filter((row) => !row.connected).map((row) => row.id);
  const fullGraphIds = rows.filter((row) => row.fullGraphExecution).map((row) => row.id);
  const directT2iIds = rows.filter((row) => row.executionMode === "generation-job-direct-t2i").map((row) => row.id);

  return {
    rows,
    connectedIds,
    disconnectedIds,
    fullGraphIds,
    directT2iIds,
    connectedCount: connectedIds.length,
    totalCount: rows.length,
    fullGraphCount: fullGraphIds.length
  };
}

export function findUiOrchestratorRouteCoverageRow(
  report: UiOrchestratorRouteCoverageReport,
  id: string
): UiOrchestratorRouteCoverageRow | undefined {
  return report.rows.find((row) => row.id === id);
}
