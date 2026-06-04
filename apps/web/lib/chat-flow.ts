import type {
  ChannelOption,
  ChatBrief,
  ChatFlowAction,
  ChatFlowState,
  CopyOption,
  InferredContext,
  ToneOption
} from "@/types/marketing";

export const toneOptions: ToneOption[] = [
  { id: "emotional", label: "감성적인", icon: "heart" },
  { id: "fresh", label: "상큼한", icon: "leaf" },
  { id: "premium", label: "고급스러운", icon: "diamond" },
  { id: "cute", label: "귀여운", icon: "smile" },
  { id: "clean", label: "깔끔한", icon: "sparkles" },
  { id: "bold", label: "강렬한", icon: "star" }
];

export const channelOptions: ChannelOption[] = [
  { id: "instagram-feed", label: "인스타 피드", ratio: "1:1" },
  { id: "instagram-story", label: "인스타 스토리", ratio: "9:16" },
  { id: "poster", label: "포스터", ratio: "4:5" },
  { id: "flyer", label: "전단지", ratio: "A4" }
];

export function inferContextFromPrompt(prompt: string): InferredContext {
  const normalized = prompt.replace(/\s+/g, "");
  const businessType = normalized.includes("카페") ? "카페" : "카페";
  const itemOrService = normalized.includes("딸기라떼") ? "딸기라떼" : "대표 메뉴";
  const promotionGoal = normalized.includes("신메뉴") ? "신메뉴 출시" : "광고 홍보";

  return {
    businessType,
    itemOrService,
    promotionGoal
  };
}

export function createInitialChatFlowState(): ChatFlowState {
  return {
    entryMode: "chat_start",
    step: 1,
    progress: { current: 0, total: 4, label: "대화 시작" },
    jobId: "",
    threadId: "",
    userInput: "",
    inferredContext: {
      businessType: "",
      itemOrService: "",
      promotionGoal: ""
    },
    contextSource: "empty",
    copyCandidates: [],
    copyCandidateSource: "empty",
    copyGenerationMode: "suggest_candidates",
    selectedTone: "감성적인",
    selectedCopyId: "",
    selectedChannelId: "instagram-feed",
    customDirection: "",
    brief: null,
    generationJob: null,
    selectedReferenceTemplateId: null,
    selectedReferenceTemplateTitle: null,
    currentQuestion: null,
    conversationMessages: [],
    isLoading: false,
    errorMessage: null
  };
}

export function chatFlowReducer(state: ChatFlowState, action: ChatFlowAction): ChatFlowState {
  switch (action.type) {
    case "reset":
      return createInitialChatFlowState();
    case "submitPrompt":
      return {
        ...state,
        step: 2,
        progress: { current: 1, total: 4, label: "정보 입력" },
        userInput: action.prompt,
        copyGenerationMode: action.copyGenerationMode ?? state.copyGenerationMode,
        inferredContext: {
          businessType: "",
          itemOrService: "",
          promotionGoal: ""
        },
        contextSource: "empty",
        conversationMessages: [{ role: "user", text: action.prompt }],
        isLoading: true,
        errorMessage: null
      };
    case "backendQuestionReceived":
      return {
        ...state,
        step: 2,
        progress: { current: 1, total: 4, label: "정보 입력" },
        jobId: action.jobId,
        threadId: action.threadId,
        inferredContext: {
          businessType: action.context.businessType ?? state.inferredContext.businessType,
          itemOrService: action.context.itemOrService ?? state.inferredContext.itemOrService,
          promotionGoal: action.context.promotionGoal ?? state.inferredContext.promotionGoal
        },
        contextSource: "backend",
        currentQuestion: action.question,
        conversationMessages: [...state.conversationMessages, { role: "assistant", text: action.question.question }],
        isLoading: false,
        errorMessage: null
      };
    case "submitQuestionAnswer":
      return {
        ...state,
        conversationMessages: [...state.conversationMessages, { role: "user", text: action.label }],
        isLoading: true,
        errorMessage: null
      };
    case "backendStartSucceeded": {
      const hasBackendCopyCandidates = action.copyCandidates.length > 0;
      const nextCopyCandidates = hasBackendCopyCandidates ? action.copyCandidates : [];
      return {
        ...state,
        step: 2,
        progress: { current: 1, total: 4, label: "정보 입력" },
        userInput: action.prompt,
        jobId: action.jobId,
        threadId: action.threadId,
        inferredContext: action.context,
        contextSource: "backend",
        copyCandidates: nextCopyCandidates,
        copyCandidateSource: action.copyCandidateSource ?? (hasBackendCopyCandidates ? "backend" : "empty"),
        copyGenerationMode: action.copyGenerationMode ?? state.copyGenerationMode,
        selectedCopyId: action.recommendedCopyId || nextCopyCandidates[0]?.id || "",
        currentQuestion: null,
        conversationMessages: [
          ...state.conversationMessages,
          { role: "assistant", text: "좋아요. 필요한 정보를 모았어요. 이제 광고 문구와 분위기를 정리해볼게요." }
        ],
        isLoading: false,
        errorMessage: null
      };
    }
    case "backendRequestFailed":
      return {
        ...state,
        isLoading: false,
        errorMessage: action.message
      };
    case "beginBriefRequest":
      return {
        ...state,
        isLoading: true,
        errorMessage: null
      };
    case "selectTone":
      return {
        ...state,
        selectedTone: action.tone
      };
    case "setCopyGenerationMode":
      return {
        ...state,
        copyGenerationMode: action.copyGenerationMode
      };
    case "continueToCopy":
      return {
        ...state,
        step: 3,
        progress: { current: 3, total: 4, label: "정보 입력" }
      };
    case "selectCopy":
      return {
        ...state,
        selectedCopyId: action.copyId
      };
    case "selectChannel":
      return {
        ...state,
        selectedChannelId: action.channelId
      };
    case "setCustomDirection":
      return {
        ...state,
        customDirection: action.value
      };
    case "backendBriefSucceeded":
      return {
        ...state,
        brief: action.brief,
        isLoading: false,
        errorMessage: null
      };
    case "requestContextLoaded":
      return {
        ...state,
        userInput: state.userInput || action.draftPrompt || state.userInput,
        selectedReferenceTemplateId: action.selectedReferenceTemplateId ?? null,
        selectedReferenceTemplateTitle: action.selectedReferenceTemplateTitle ?? null
      };
    case "referenceTemplateSelected":
      return {
        ...state,
        selectedReferenceTemplateId: action.selectedReferenceTemplateId,
        selectedReferenceTemplateTitle: action.selectedReferenceTemplateTitle ?? null
      };
    case "referenceTemplateCleared":
      return {
        ...state,
        selectedReferenceTemplateId: null,
        selectedReferenceTemplateTitle: null
      };
    case "continueToBrief":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "정보 입력" },
        isLoading: false
      };
    case "showResultShell":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "결과 확인" },
        isLoading: false,
        currentQuestion: null,
        errorMessage: null
      };
    case "back":
      return {
        ...state,
        step: Math.max(1, state.step - 1) as ChatFlowState["step"]
      };
    default:
      return state;
    case "generationJobRequested":
      return {
        ...state,
        isLoading: true,
        errorMessage: null
      };

    case "generationJobUpdated":
      return {
        ...state,
        generationJob: action.generationJob,
        isLoading: false,
        errorMessage: null
      };

    case "generationJobFailed":
      return {
        ...state,
        isLoading: false,
        errorMessage: action.message
      };
  }
}

export function selectedCopyLabel(state: ChatFlowState): string {
  return state.copyCandidates.find((copy) => copy.id === state.selectedCopyId)?.headline ?? "";
}

export function selectedChannelLabel(state: ChatFlowState): string {
  const channel = channelOptions.find((item) => item.id === state.selectedChannelId) ?? channelOptions[0];
  return `${channel.label} (${channel.ratio})`;
}

export function selectedToneSummary(state: ChatFlowState): string {
  return state.selectedTone ? `${state.selectedTone} 분위기` : "브랜드에 맞춘 분위기";
}

export function fallbackImageDirection(state: ChatFlowState): string {
  if (state.customDirection) {
    return state.customDirection;
  }
  const item = state.inferredContext.itemOrService || "상품/서비스";
  const tonePrefix = state.selectedTone ? `${state.selectedTone} 분위기를 살려 ` : "";
  if (item.includes("예약") || item.endsWith("서비스")) {
    return `${tonePrefix}${item} 안내가 잘 보이도록 깔끔한 배경과 읽기 쉬운 여백을 구성해요.`;
  }
  return `${tonePrefix}${item} 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.`;
}

export function buildBrief(state: ChatFlowState): ChatBrief {
  if (state.brief) {
    return state.brief;
  }
  return {
    purpose: state.inferredContext.promotionGoal,
    item: state.inferredContext.itemOrService,
    copy: selectedCopyLabel(state),
    tone: selectedToneSummary(state),
    channel: selectedChannelLabel(state),
    imageDirection: fallbackImageDirection(state)
  };
}
