export type UiOrchestratorExecutionMode =
  | "langgraph-interrupt-loop"
  | "langgraph-resume"
  | "generation-job-direct-t2i"
  | "generation-job-graph"
  | "ui-only";

export type UiOrchestratorRouteCoverageRow = {
  id: string;
  label: string;
  userFlow: string;
  uiEntryPoints: string[];
  apiCalls: string[];
  executionMode: UiOrchestratorExecutionMode;
  connected: boolean;
  fullGraphExecution: boolean;
  graphNodesReached: string[];
  graphNodesBypassed: string[];
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
    uiEntryPoints: ["ChatStartStep", "ChatContextQuestionStep"],
    apiCalls: ["POST /api/generate/chat/start", "POST /api/generate/chat/answer"],
    executionMode: "langgraph-interrupt-loop",
    connected: true,
    fullGraphExecution: false,
    graphNodesReached: ["input", "validator", "options", "state_update"],
    graphNodesBypassed: FINAL_GENERATION_GRAPH_CHAIN,
    notes: "초기 컨텍스트 수집 루프는 LangGraph interrupt/resume로 연결되어 있지만, 최종 이미지 생성 체인까지 실행하는 단계는 아니다."
  },
  {
    id: "brief-confirmation",
    label: "브리프 확인",
    userFlow: "문구/채널/톤 선택 후 브리프 확인",
    uiEntryPoints: ["CopyChannelStep", "BriefConfirmStep"],
    apiCalls: ["POST /api/generate/chat/brief"],
    executionMode: "langgraph-resume",
    connected: true,
    fullGraphExecution: false,
    graphNodesReached: ["copy_candidate_selection_interrupt", "state_update_selected_copy", "copy_spec_parser"],
    graphNodesBypassed: ["t2i_generation", "background_validation", "safe_area_gate", "text_renderer", "readability_gate", "final_validation", "result"],
    notes: "사용자 선택값은 graph resume으로 들어가지만, UI는 이 단계에서 실제 이미지 생성/검증 결과를 받지 않는다."
  },
  {
    id: "final-model-generation",
    label: "모델 선택 최종 이미지 생성",
    userFlow: "GPT-image-2, FLUX.1-schnell, SD3.5 Large 중 하나를 선택해 최종 생성",
    uiEntryPoints: ["GenerationEngineSelector", "BriefConfirmStep", "GenerationInProgressStep", "GenerationCompleteStep"],
    apiCalls: ["POST /api/generation-jobs", "GET /api/generation-jobs/{job_id}"],
    executionMode: "generation-job-graph",
    connected: true,
    fullGraphExecution: true,
    graphNodesReached: FINAL_GENERATION_GRAPH_CHAIN,
    graphNodesBypassed: [],
    notes: "현재 UI의 모델 선택은 graph_immediate generation job으로 전달되며, 선택 엔진은 graph state의 engine preference로 t2i_generation 노드까지 전달된다."
  },
  {
    id: "reference-template-selection",
    label: "레퍼런스 템플릿 선택",
    userFlow: "레퍼런스 갤러리에서 템플릿을 선택해 다음 생성 요청에 전달",
    uiEntryPoints: ["ReferenceBrowseStep", "ChatStartStep"],
    apiCalls: ["GET /api/references", "POST /api/generate/chat/start", "POST /api/generation-jobs"],
    executionMode: "langgraph-interrupt-loop",
    connected: true,
    fullGraphExecution: false,
    graphNodesReached: ["reference_template_resolve", "validator", "image_prompt_planner"],
    graphNodesBypassed: ["background_validation", "safe_area_gate", "readability_gate", "final_validation"],
    notes: "템플릿 id는 graph 시작과 final graph generation job에 전달되며, 최종 이미지 생성의 style hint로 이어진다."
  },
  {
    id: "reference-image-upload",
    label: "레퍼런스 이미지 업로드",
    userFlow: "사용자가 스타일 참조 이미지를 직접 업로드",
    uiEntryPoints: [],
    apiCalls: [],
    executionMode: "ui-only",
    connected: false,
    fullGraphExecution: false,
    graphNodesReached: [],
    graphNodesBypassed: ["reference_preprocess", "image_prompt_planner"],
    notes: "graph에는 reference_preprocess 노드가 있지만 UI 업로드 경로가 아직 없다."
  },
  {
    id: "validation-feedback",
    label: "검증 결과 피드백",
    userFlow: "생성 후 safe area/readability/final validation 결과 확인",
    uiEntryPoints: [],
    apiCalls: [],
    executionMode: "ui-only",
    connected: false,
    fullGraphExecution: false,
    graphNodesReached: [],
    graphNodesBypassed: ["background_validation", "safe_area_gate", "readability_gate", "final_validation"],
    notes: "graph 검증 노드 결과를 사용자 화면에 노출하는 UI가 아직 없다."
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
