import type {
  ChannelOption,
  ChatBrief,
  ChatFlowAction,
  ChatFlowState,
  CopyOption,
  InferredContext,
  ToneOption
} from "@/types/marketing";
import { DEFAULT_IMAGE_GENERATION_ENGINE } from "./generation-engine";

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
    copyCandidateOrigin: "unknown",
    copyGenerationMode: "suggest_candidates",
    selectedTone: "감성적인",
    selectedCopyId: "",
    selectedChannelId: "instagram-feed",
    customDirection: "",
    userCustomHeadline: "",
    userCustomSubcopy: "",
    brief: null,
    generationJob: null,
    selectedImageGenerationEngine: DEFAULT_IMAGE_GENERATION_ENGINE,
    selectedReferenceTemplateId: null,
    selectedReferenceTemplateTitle: null,
    sourceImagePath: null,
    referenceImagePath: null,
    currentQuestion: null,
    conversationMessages: [],
    isLoading: false,
    errorMessage: null,
    errorCode: null
  };
}

function applyUserPromptToTranscript(
  messages: ChatFlowState["conversationMessages"],
  prompt: string,
  mode: "append" | "update_current_turn" = "append"
): ChatFlowState["conversationMessages"] {
  if (mode === "update_current_turn") {
    let lastUserIndex = -1;
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index]?.role === "user") {
        lastUserIndex = index;
        break;
      }
    }
    if (lastUserIndex >= 0) {
      return messages.map((message, index) => (index === lastUserIndex ? { ...message, text: prompt } : message));
    }
  }
  return [...messages, { role: "user", text: prompt }];
}

function appendAssistantMessageOnce(
  messages: ChatFlowState["conversationMessages"],
  text: string
): ChatFlowState["conversationMessages"] {
  const lastMessage = messages[messages.length - 1];
  if (lastMessage?.role === "assistant" && lastMessage.text === text) {
    return messages;
  }
  return [...messages, { role: "assistant", text }];
}

function isGenerationJobTerminalStatus(status: string): boolean {
  return status === "done" || status === "failed" || status === "cancelled";
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
        sourceImagePath: action.sourceImagePath ?? null,
        referenceImagePath: action.referenceImagePath ?? null,
        userCustomHeadline: action.userCustomHeadline ?? "",
        userCustomSubcopy: action.userCustomSubcopy ?? "",
        copyGenerationMode: action.copyGenerationMode ?? state.copyGenerationMode,
        selectedImageGenerationEngine: action.imageGenerationEngine ?? state.selectedImageGenerationEngine,
        inferredContext: {
          businessType: "",
          itemOrService: "",
          promotionGoal: ""
        },
        contextSource: "empty",
        conversationMessages: applyUserPromptToTranscript(state.conversationMessages, action.prompt, action.transcriptMode),
        isLoading: true,
        errorMessage: null,
        errorCode: null
      };
    case "backendQuestionReceived":
      return {
        ...state,
        step: 2,
        progress: { current: 1, total: 4, label: "정보 입력" },
        jobId: action.jobId,
        threadId: action.threadId,
        generationJob: action.generationJob ?? state.generationJob,
        sourceImagePath: action.sourceImagePath ?? state.sourceImagePath ?? null,
        referenceImagePath: action.referenceImagePath ?? state.referenceImagePath ?? null,
        inferredContext: {
          businessType: action.context.businessType ?? state.inferredContext.businessType,
          itemOrService: action.context.itemOrService ?? state.inferredContext.itemOrService,
          promotionGoal: action.context.promotionGoal ?? state.inferredContext.promotionGoal
        },
        contextSource: "backend",
        currentQuestion: action.question,
        conversationMessages: appendAssistantMessageOnce(state.conversationMessages, action.question.question),
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };
    case "submitQuestionAnswer":
      return {
        ...state,
        conversationMessages: [...state.conversationMessages, { role: "user", text: action.label }],
        isLoading: true,
        errorMessage: null,
        errorCode: null
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
        copyCandidateOrigin: hasBackendCopyCandidates ? action.copyCandidateOrigin ?? "unknown" : "unknown",
        copyGenerationMode: action.copyGenerationMode ?? state.copyGenerationMode,
        selectedImageGenerationEngine: action.imageGenerationEngine ?? state.selectedImageGenerationEngine,
        sourceImagePath: action.sourceImagePath ?? state.sourceImagePath ?? null,
        referenceImagePath: action.referenceImagePath ?? state.referenceImagePath ?? null,
        userCustomHeadline: action.userCustomHeadline ?? state.userCustomHeadline,
        userCustomSubcopy: action.userCustomSubcopy ?? state.userCustomSubcopy,
        selectedCopyId: action.recommendedCopyId || nextCopyCandidates[0]?.id || "",
        currentQuestion: null,
        conversationMessages: [
          ...state.conversationMessages,
          { role: "assistant", text: "좋아요. 필요한 정보를 모았어요. 이제 광고 문구와 분위기를 정리해볼게요." }
        ],
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };
    }
    case "backendRequestFailed":
      if (action.recoverToStart) {
        return {
          ...state,
          step: 1,
          progress: { current: 0, total: 4, label: "대화 시작" },
          currentQuestion: null,
          isLoading: false,
          errorMessage: action.message,
          errorCode: action.errorCode ?? null
        };
      }
      return {
        ...state,
        isLoading: false,
        errorMessage: action.message,
        errorCode: action.errorCode ?? null
      };
    case "beginBriefRequest":
      return {
        ...state,
        isLoading: true,
        errorMessage: null,
        errorCode: null
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
    case "setImageGenerationEngine":
      return {
        ...state,
        selectedImageGenerationEngine: action.imageGenerationEngine
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
    case "submitBriefRefinement":
      return {
        ...state,
        customDirection: action.customDirection,
        conversationMessages: [...state.conversationMessages, { role: "user", text: action.message }],
        isLoading: true,
        errorMessage: null,
        errorCode: null
      };
    case "backendBriefSucceeded":
      return {
        ...state,
        brief: action.brief,
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };
    case "briefRefinementSucceeded":
      return {
        ...state,
        brief: action.brief,
        conversationMessages: [
          ...state.conversationMessages,
          { role: "assistant", text: "좋아요. 요청을 반영해서 브리프를 다시 정리했어요." }
        ],
        isLoading: false,
        errorMessage: null,
        errorCode: null
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
    case "restoreThreadSnapshot":
      return {
        ...state,
        step: 4,
        progress: {
          current: 4,
          total: 4,
          label: action.currentQuestion ? "추가 정보" : "정보 입력"
        },
        userInput: action.prompt,
        jobId: action.jobId,
        threadId: action.threadId,
        inferredContext: action.context,
        contextSource: "backend",
        copyGenerationMode: action.copyGenerationMode,
        copyCandidates: action.copyCandidates,
        copyCandidateSource: action.copyCandidates.length > 0 ? "backend" : "empty",
        copyCandidateOrigin: action.copyCandidateOrigin,
        selectedCopyId: action.selectedCopyId,
        selectedChannelId: action.selectedChannelId,
        selectedTone: action.selectedTone,
        selectedImageGenerationEngine: action.selectedImageGenerationEngine,
        customDirection: action.customDirection,
        userCustomHeadline: action.userCustomHeadline,
        userCustomSubcopy: action.userCustomSubcopy,
        sourceImagePath: action.sourceImagePath,
        referenceImagePath: action.referenceImagePath,
        selectedReferenceTemplateId: action.selectedReferenceTemplateId,
        selectedReferenceTemplateTitle: action.selectedReferenceTemplateTitle,
        generationJob: action.generationJob,
        currentQuestion: action.currentQuestion,
        conversationMessages:
          action.conversationMessages.length > 0
            ? action.conversationMessages
            : action.prompt
              ? [{ role: "user", text: action.prompt }]
              : state.conversationMessages,
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };
    case "showResultShell":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "결과 확인" },
        isLoading: false,
        currentQuestion: null,
        errorMessage: null,
        errorCode: null
      };
    case "showGenerationFailure":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "생성 실패" },
        threadId: action.threadId ?? state.threadId,
        userInput: action.userInput ?? state.userInput,
        selectedImageGenerationEngine: action.imageGenerationEngine ?? state.selectedImageGenerationEngine,
        generationJob: null,
        isLoading: false,
        currentQuestion: null,
        errorMessage: action.message,
        errorCode: null
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
        errorMessage: null,
        errorCode: null
      };

    case "generationJobUpdated":
      const shouldKeepInitialAnalysisPending =
        state.step === 2 &&
        !state.currentQuestion &&
        action.generationJob.status !== "waiting_user_input" &&
        !isGenerationJobTerminalStatus(action.generationJob.status);
      const shouldKeepAnswerPending =
        state.step === 4 &&
        state.isLoading &&
        action.generationJob.status !== "waiting_user_input" &&
        !isGenerationJobTerminalStatus(action.generationJob.status);

      return {
        ...state,
        jobId: action.generationJob.job_id ?? state.jobId,
        threadId: action.generationJob.thread_id ?? state.threadId,
        generationJob: action.generationJob,
        currentQuestion: action.generationJob.status === "waiting_user_input" ? state.currentQuestion : null,
        isLoading: shouldKeepInitialAnalysisPending || shouldKeepAnswerPending,
        errorMessage: null,
        errorCode: null
      };

    case "generationJobQuestionReceived":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "추가 정보" },
        generationJob: action.generationJob,
        sourceImagePath: action.sourceImagePath ?? state.sourceImagePath ?? null,
        referenceImagePath: action.referenceImagePath ?? state.referenceImagePath ?? null,
        inferredContext: {
          businessType: action.context?.businessType ?? state.inferredContext.businessType,
          itemOrService: action.context?.itemOrService ?? state.inferredContext.itemOrService,
          promotionGoal: action.context?.promotionGoal ?? state.inferredContext.promotionGoal
        },
        contextSource: action.context ? "backend" : state.contextSource,
        currentQuestion: action.question,
        conversationMessages: appendAssistantMessageOnce(state.conversationMessages, action.question.question),
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };

    case "generationJobInterruptReceived":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "추가 선택" },
        generationJob: action.generationJob,
        currentQuestion: null,
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };

    case "submitGenerationJobAnswer":
      return {
        ...state,
        conversationMessages: [...state.conversationMessages, { role: "user", text: action.label }],
        isLoading: true,
        errorMessage: null,
        errorCode: null
      };

    case "generationJobFailed":
      return {
        ...state,
        isLoading: false,
        errorMessage: action.message,
        errorCode: null
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
