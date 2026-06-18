import type {
  ChatBrief,
  ChatFlowAction,
  ChatFlowState,
  CopyOption,
  InferredContext,
  ToneOption
} from "@/types/marketing";
import { campaignIntentLabel, contextItemSummary, contextPurposeSummary } from "./context-presentation";
import { channelOptions } from "./ad-formats";
import { DEFAULT_IMAGE_GENERATION_ENGINE, getGenerationEngineOption, type ImageGenerationEngine } from "./generation-engine";

export { channelOptions } from "./ad-formats";

export const toneOptions: ToneOption[] = [
  { id: "emotional", label: "감성적인", icon: "heart" },
  { id: "fresh", label: "상큼한", icon: "leaf" },
  { id: "premium", label: "고급스러운", icon: "diamond" },
  { id: "cute", label: "귀여운", icon: "smile" },
  { id: "clean", label: "깔끔한", icon: "sparkles" },
  { id: "bold", label: "강렬한", icon: "star" }
];

const CHAT_ERROR_MESSAGE_BY_CODE: Partial<Record<string, string>> = {
  thread_limit_reached:
    "\ube44\ub85c\uadf8\uc778 \uc0c1\ud0dc\uc5d0\uc11c\ub294 \uc791\uc5c5\ubc29\uc744 3\uac1c\uae4c\uc9c0 \ub9cc\ub4e4 \uc218 \uc788\uc5b4\uc694. \uae30\uc874 \uc791\uc5c5\ubc29\uc744 \uc0ad\uc81c\ud558\uac70\ub098 \ub85c\uadf8\uc778\ud558\uba74 \uacc4\uc18d \ub9cc\ub4e4 \uc218 \uc788\uc5b4\uc694.",
  workspace_required: "\uc791\uc5c5\ubc29\uc744 \uc900\ube44\ud558\uc9c0 \ubabb\ud588\uc5b4\uc694. \uc7a0\uc2dc \ud6c4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.",
  archive_workspace_required: "\ubcf4\uad00\ud568\uc744 \uc900\ube44\ud558\uc9c0 \ubabb\ud588\uc5b4\uc694. \uc7a0\uc2dc \ud6c4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.",
  usage_workspace_required: "\uc0ac\uc6a9\ub7c9 \uc815\ubcf4\ub97c \ubd88\ub7ec\uc624\uc9c0 \ubabb\ud588\uc5b4\uc694. \uc7a0\uc2dc \ud6c4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.",
  invalid_or_expired_session: "\ub85c\uadf8\uc778\uc774 \ub9cc\ub8cc\ub410\uc5b4\uc694. \ub2e4\uc2dc \ub85c\uadf8\uc778\ud55c \ub4a4 \uc774\uc5b4\uc11c \uc9c4\ud589\ud574 \uc8fc\uc138\uc694.",
  supabase_auth_configuration_missing: "\ub85c\uadf8\uc778 \uc124\uc815\uc744 \ud655\uc778\ud574\uc57c \ud574\uc694. \uad00\ub9ac\uc790\uc5d0\uac8c \ubb38\uc758\ud574 \uc8fc\uc138\uc694.",
  upstream_orchestrator_unavailable: "\uc0dd\uc131 \uc11c\ubc84\uc5d0 \uc5f0\uacb0\ud558\uc9c0 \ubabb\ud588\uc5b4\uc694. \uc785\ub825 \ub0b4\uc6a9\uc740 \uc720\uc9c0\ud588\uc73c\ub2c8 \uc7a0\uc2dc \ud6c4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694."
};

const CHAT_FALLBACK_ERROR_MESSAGE = "\uc694\uccad \ucc98\ub9ac \uc911 \ubb38\uc81c\uac00 \uc0dd\uacbc\uc5b4\uc694. \uc7a0\uc2dc \ud6c4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.";

export type ChatFailureLike = {
  errorCode?: string | null;
  message?: string | null;
};

export function chatFailureFromError(error: ChatFailureLike): { message: string; errorCode: string | null } {
  const errorCode = error.errorCode ?? null;
  const mappedMessage = errorCode ? CHAT_ERROR_MESSAGE_BY_CODE[errorCode] : undefined;
  const fallbackMessage = error.message?.trim() ? error.message : CHAT_FALLBACK_ERROR_MESSAGE;

  return {
    message: mappedMessage ?? fallbackMessage,
    errorCode
  };
}

export function inferContextFromPrompt(prompt: string): InferredContext {
  void prompt;
  return {
    businessType: null,
    itemOrService: null,
    promotionGoal: null,
    advertisedSubject: null,
    advertisedSubjectType: null,
    campaignIntent: null
  };
}

const QUESTION_FIELD_TO_CONTEXT_KEY: Partial<Record<string, keyof InferredContext>> = {
  business_type: "businessType",
  item_or_service: "itemOrService",
  promotion_goal: "promotionGoal",
  campaign_intent: "campaignIntent",
  advertised_subject: "advertisedSubject",
  advertised_subject_type: "advertisedSubjectType"
};

export function contextPatchFromQuestionAnswer(input: {
  field: string;
  value: string;
}): Partial<InferredContext> {
  const key = QUESTION_FIELD_TO_CONTEXT_KEY[input.field];
  if (!key || !input.value || input.value === "custom") {
    return {};
  }
  return { [key]: input.value };
}

export function hasMeaningfulContext(
  context: Partial<InferredContext> | null | undefined
): boolean {
  if (!context) return false;
  return Boolean(
    context.businessType ||
    context.itemOrService ||
    context.promotionGoal ||
    context.campaignIntent ||
    context.advertisedSubject
  );
}

export function mergeInferredContext(
  current: InferredContext,
  incoming: Partial<InferredContext> | null | undefined
): InferredContext {
  return {
    businessType: incoming?.businessType ?? current.businessType ?? null,
    itemOrService: incoming?.itemOrService ?? current.itemOrService ?? null,
    promotionGoal: incoming?.promotionGoal ?? current.promotionGoal ?? null,
    advertisedSubject: incoming?.advertisedSubject ?? current.advertisedSubject ?? null,
    advertisedSubjectType: incoming?.advertisedSubjectType ?? current.advertisedSubjectType ?? null,
    campaignIntent: incoming?.campaignIntent ?? current.campaignIntent ?? null
  };
}

export function createInitialChatFlowState(): ChatFlowState {
  return {
    entryMode: "chat_start",
    step: 1,
    progress: { current: 0, total: 4, label: "\ub300\ud654 \uc2dc\uc791" },
    jobId: "",
    threadId: "",
    userInput: "",
    inferredContext: {
      businessType: null,
      itemOrService: null,
      promotionGoal: null,
      advertisedSubject: null,
      advertisedSubjectType: null,
      campaignIntent: null
    },
    contextSource: "empty",
    copyCandidates: [],
    copyCandidateSource: "empty",
    copyCandidateOrigin: "unknown",
    copyFallbackUsed: false,
    copyFallbackReason: null,
    copyGenerationMode: "suggest_candidates",
    selectedTone: "\uac10\uc131\uc801\uc778",
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
    sourceAssetId: null,
    sourceImagePath: null,
    referenceImagePath: null,
    pendingExplicitContextPatch: null,
    currentQuestion: null,
    conversationMessages: [],
    isLoading: false,
    errorMessage: null,
    errorCode: null
  };
}

function progressFromQuestion(
  question: { progressState?: ChatFlowState["progress"] | null } | null | undefined,
  fallback: ChatFlowState["progress"]
): ChatFlowState["progress"] {
  const progress = question?.progressState;
  if (!progress) {
    return fallback;
  }
  return { current: progress.current, total: progress.total, label: progress.label };
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

function normalizeImageGenerationEngine(engine: ImageGenerationEngine | null | undefined): ImageGenerationEngine {
  return getGenerationEngineOption(engine).id;
}

export function chatFlowReducer(state: ChatFlowState, action: ChatFlowAction): ChatFlowState {
  switch (action.type) {
    case "reset":
      return createInitialChatFlowState();
    case "submitPrompt":
      return {
        ...state,
        step: 2,
        progress: { current: 1, total: 4, label: "\uc815\ubcf4 \uc785\ub825" },
        userInput: action.prompt,
        sourceAssetId: action.sourceAssetId ?? null,
        sourceImagePath: action.sourceImagePath ?? null,
        referenceImagePath: action.referenceImagePath ?? null,
        userCustomHeadline: action.userCustomHeadline ?? "",
        userCustomSubcopy: action.userCustomSubcopy ?? "",
        copyGenerationMode: action.copyGenerationMode ?? state.copyGenerationMode,
        selectedImageGenerationEngine: normalizeImageGenerationEngine(
          action.imageGenerationEngine ?? state.selectedImageGenerationEngine
        ),
        inferredContext: {
          businessType: null,
          itemOrService: null,
          promotionGoal: null,
          advertisedSubject: null,
          advertisedSubjectType: null,
          campaignIntent: null
        },
        contextSource: "empty",
        pendingExplicitContextPatch: null,
        conversationMessages: applyUserPromptToTranscript(state.conversationMessages, action.prompt, action.transcriptMode),
        isLoading: true,
        errorMessage: null,
        errorCode: null
      };
    case "backendQuestionReceived": {
      const backendMerged = mergeInferredContext(state.inferredContext, action.context);
      const finalContext = mergeInferredContext(backendMerged, state.pendingExplicitContextPatch);
      return {
        ...state,
        step: 2,
        progress: action.progress ?? progressFromQuestion(action.question, { current: 1, total: 4, label: "\uc815\ubcf4 \uc785\ub825" }),
        jobId: action.jobId,
        threadId: action.threadId,
        generationJob: action.generationJob ?? state.generationJob,
        sourceAssetId: action.sourceAssetId ?? state.sourceAssetId ?? null,
        sourceImagePath: action.sourceImagePath ?? state.sourceImagePath ?? null,
        referenceImagePath: action.referenceImagePath ?? state.referenceImagePath ?? null,
        selectedChannelId: action.selectedChannelId ?? state.selectedChannelId,
        inferredContext: finalContext,
        contextSource: "backend",
        pendingExplicitContextPatch: null,
        currentQuestion: action.question,
        conversationMessages: appendAssistantMessageOnce(state.conversationMessages, action.question.question),
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };
    }
    case "submitQuestionAnswer": {
      const explicitPatch =
        action.field && action.value
          ? contextPatchFromQuestionAnswer({ field: action.field, value: action.value })
          : {};
      const hasExplicit = Object.keys(explicitPatch).length > 0;
      return {
        ...state,
        inferredContext: hasExplicit
          ? mergeInferredContext(state.inferredContext, explicitPatch)
          : state.inferredContext,
        pendingExplicitContextPatch: hasExplicit ? explicitPatch : state.pendingExplicitContextPatch,
        conversationMessages: [...state.conversationMessages, { role: "user", text: action.label }],
        isLoading: true,
        errorMessage: null,
        errorCode: null
      };
    }
    case "backendStartSucceeded": {
      const hasBackendCopyCandidates = action.copyCandidates.length > 0;
      const nextCopyCandidates = hasBackendCopyCandidates ? action.copyCandidates : [];
      const backendMergedStart = mergeInferredContext(state.inferredContext, action.context);
      const finalContextStart = mergeInferredContext(backendMergedStart, state.pendingExplicitContextPatch);
      return {
        ...state,
        step: 2,
        progress: { current: 1, total: 4, label: "\uc815\ubcf4 \uc785\ub825" },
        userInput: action.prompt,
        jobId: action.jobId,
        threadId: action.threadId,
        inferredContext: finalContextStart,
        contextSource: "backend",
        pendingExplicitContextPatch: null,
        copyCandidates: nextCopyCandidates,
        copyCandidateSource: action.copyCandidateSource ?? (hasBackendCopyCandidates ? "backend" : "empty"),
        copyCandidateOrigin: hasBackendCopyCandidates ? action.copyCandidateOrigin ?? "unknown" : "unknown",
        copyFallbackUsed: hasBackendCopyCandidates ? action.copyFallbackUsed ?? false : false,
        copyFallbackReason: hasBackendCopyCandidates ? action.copyFallbackReason ?? null : null,
        copyGenerationMode: action.copyGenerationMode ?? state.copyGenerationMode,
        selectedImageGenerationEngine: normalizeImageGenerationEngine(
          action.imageGenerationEngine ?? state.selectedImageGenerationEngine
        ),
        sourceAssetId: action.sourceAssetId ?? state.sourceAssetId ?? null,
        sourceImagePath: action.sourceImagePath ?? state.sourceImagePath ?? null,
        referenceImagePath: action.referenceImagePath ?? state.referenceImagePath ?? null,
        userCustomHeadline: action.userCustomHeadline ?? state.userCustomHeadline,
        userCustomSubcopy: action.userCustomSubcopy ?? state.userCustomSubcopy,
        selectedChannelId: action.selectedChannelId ?? state.selectedChannelId,
        selectedCopyId: action.recommendedCopyId || nextCopyCandidates[0]?.id || "",
        currentQuestion: null,
        conversationMessages: [
          ...state.conversationMessages,
          { role: "assistant", text: "\uc88b\uc544\uc694. \ud544\uc694\ud55c \uc815\ubcf4\ub97c \ubaa8\uc558\uc5b4\uc694. \uc774\uc81c \uad11\uace0 \ubb38\uad6c\uc640 \ubd84\uc704\uae30\ub97c \uc815\ub9ac\ud574\ubcfc\uac8c\uc694." }
        ],
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };
    }
    case "backendRequestFailed":
      const backendFailure = chatFailureFromError(action);
      if (action.recoverToStart && backendFailure.errorCode === "thread_limit_reached") {
        return {
          ...state,
          step: 1,
          progress: { current: 0, total: 4, label: "\ub300\ud654 \uc2dc\uc791" },
          currentQuestion: null,
          isLoading: false,
          errorMessage: backendFailure.message,
          errorCode: backendFailure.errorCode
        };
      }
      if (action.recoverToStart) {
        return {
          ...state,
          progress: { ...state.progress, label: "\uc791\uc5c5 \uc2dc\uc791 \uc2e4\ud328" },
          currentQuestion: null,
          isLoading: false,
          errorMessage: backendFailure.message,
          errorCode: backendFailure.errorCode
        };
      }
      return {
        ...state,
        isLoading: false,
        errorMessage: backendFailure.message,
        errorCode: backendFailure.errorCode
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
        selectedImageGenerationEngine: normalizeImageGenerationEngine(action.imageGenerationEngine)
      };
    case "continueToCopy":
      return {
        ...state,
        step: 3,
        progress: { current: 3, total: 4, label: "\uc815\ubcf4 \uc785\ub825" }
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
          { role: "assistant", text: "\uc88b\uc544\uc694. \uc694\uccad\uc744 \ubc18\uc601\ud574\uc11c \ube0c\ub9ac\ud504\ub97c \ub2e4\uc2dc \uc815\ub9ac\ud588\uc5b4\uc694." }
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
        progress: { current: 4, total: 4, label: "\uc815\ubcf4 \uc785\ub825" },
        isLoading: false
      };
    case "restoreThreadSnapshot": {
      const snapshotMerged = mergeInferredContext(state.inferredContext, action.context);
      const finalRestoreContext = mergeInferredContext(snapshotMerged, state.pendingExplicitContextPatch);
      return {
        ...state,
        step: 4,
        progress: action.currentQuestion
          ? progressFromQuestion(action.currentQuestion, {
              current: 4,
              total: 4,
              label: "\ucd94\uac00 \uc815\ubcf4"
            })
          : {
              current: 4,
              total: 4,
              label: "\uc815\ubcf4 \uc785\ub825"
            },
        userInput: action.prompt,
        jobId: action.jobId,
        threadId: action.threadId,
        inferredContext: finalRestoreContext,
        contextSource: hasMeaningfulContext(action.context) ? "backend" : state.contextSource,
        pendingExplicitContextPatch: state.pendingExplicitContextPatch,
        copyGenerationMode: action.copyGenerationMode,
        copyCandidates: action.copyCandidates,
        copyCandidateSource: action.copyCandidates.length > 0 ? "backend" : "empty",
        copyCandidateOrigin: action.copyCandidateOrigin,
        copyFallbackUsed: action.copyFallbackUsed ?? false,
        copyFallbackReason: action.copyFallbackReason ?? null,
        selectedCopyId: action.selectedCopyId,
        selectedChannelId: action.selectedChannelId ?? state.selectedChannelId,
        selectedTone: action.selectedTone,
        selectedImageGenerationEngine: normalizeImageGenerationEngine(action.selectedImageGenerationEngine),
        customDirection: action.customDirection,
        userCustomHeadline: action.userCustomHeadline,
        userCustomSubcopy: action.userCustomSubcopy,
        sourceAssetId: action.sourceAssetId ?? null,
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
    }
    case "showResultShell":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "\uacb0\uacfc \ud655\uc778" },
        isLoading: false,
        currentQuestion: null,
        errorMessage: null,
        errorCode: null
      };
    case "showGenerationFailure":
      const generationFailure = chatFailureFromError(action);
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "\uc0dd\uc131 \uc2e4\ud328" },
        threadId: action.threadId ?? state.threadId,
        userInput: action.userInput ?? state.userInput,
        selectedImageGenerationEngine: normalizeImageGenerationEngine(
          action.imageGenerationEngine ?? state.selectedImageGenerationEngine
        ),
        generationJob: null,
        isLoading: false,
        currentQuestion: null,
        errorMessage: generationFailure.message,
        errorCode: generationFailure.errorCode
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

    case "generationJobQuestionReceived": {
      const backendMergedJob = mergeInferredContext(state.inferredContext, action.context);
      const finalContextJob = mergeInferredContext(backendMergedJob, state.pendingExplicitContextPatch);
      return {
        ...state,
        step: 4,
        progress: action.progress ?? progressFromQuestion(action.question, { current: 4, total: 4, label: "\ucd94\uac00 \uc815\ubcf4" }),
        generationJob: action.generationJob,
        sourceAssetId: action.sourceAssetId ?? state.sourceAssetId ?? null,
        sourceImagePath: action.sourceImagePath ?? state.sourceImagePath ?? null,
        referenceImagePath: action.referenceImagePath ?? state.referenceImagePath ?? null,
        inferredContext: finalContextJob,
        contextSource: hasMeaningfulContext(action.context) ? "backend" : state.contextSource,
        pendingExplicitContextPatch: hasMeaningfulContext(action.context) ? null : state.pendingExplicitContextPatch,
        currentQuestion: action.question,
        conversationMessages: appendAssistantMessageOnce(state.conversationMessages, action.question.question),
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };
    }

    case "generationJobInterruptReceived":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "\ucd94\uac00 \uc120\ud0dd" },
        generationJob: action.generationJob,
        currentQuestion: null,
        isLoading: false,
        errorMessage: null,
        errorCode: null
      };

    case "submitGenerationJobAnswer": {
      const jobExplicitPatch =
        action.field && action.value
          ? contextPatchFromQuestionAnswer({ field: action.field, value: action.value })
          : {};
      const hasJobExplicit = Object.keys(jobExplicitPatch).length > 0;
      return {
        ...state,
        inferredContext: hasJobExplicit
          ? mergeInferredContext(state.inferredContext, jobExplicitPatch)
          : state.inferredContext,
        pendingExplicitContextPatch: hasJobExplicit ? jobExplicitPatch : state.pendingExplicitContextPatch,
        conversationMessages: [...state.conversationMessages, { role: "user", text: action.label }],
        isLoading: true,
        errorMessage: null,
        errorCode: null
      };
    }

    case "generationJobFailed":
      const generationJobFailure = chatFailureFromError(action);
      return {
        ...state,
        isLoading: false,
        errorMessage: generationJobFailure.message,
        errorCode: generationJobFailure.errorCode
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
  return state.selectedTone ? `${state.selectedTone} \ubd84\uc704\uae30` : "\ube0c\ub79c\ub4dc\uc5d0 \ub9de\ub294 \ubd84\uc704\uae30";
}

function contextItemLabel(context: InferredContext): string {
  return contextItemSummary(context) || "상품/서비스";
}

function contextPurposeLabel(context: InferredContext): string {
  if (context.promotionGoal) {
    return context.promotionGoal;
  }
  return campaignIntentLabel(context.campaignIntent) || "";
}

export function fallbackImageDirection(state: ChatFlowState): string {
  if (state.customDirection) {
    return state.customDirection;
  }
  const item = contextItemLabel(state.inferredContext);
  const tonePrefix = state.selectedTone ? `${state.selectedTone} 분위기를 살려 ` : "";
  if (item.includes("예약") || item.endsWith("서비스")) {
    return `${tonePrefix}${item} 안내가 잘 보이도록 깔끔한 배경과 구도로 구성해요.`;
  }
  return `${tonePrefix}${item} 중심의 깔끔한 광고 구도로 구성해요.`;
}

export function buildBrief(state: ChatFlowState): ChatBrief {
  if (state.brief) {
    return state.brief;
  }
  return {
    purpose: contextPurposeLabel(state.inferredContext),
    item: contextItemLabel(state.inferredContext),
    copy: selectedCopyLabel(state),
    tone: selectedToneSummary(state),
    channel: selectedChannelLabel(state),
    selectedChannelId: state.selectedChannelId,
    imageDirection: fallbackImageDirection(state)
  };
}
