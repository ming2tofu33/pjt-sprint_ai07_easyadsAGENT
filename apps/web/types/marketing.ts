import type { GenerationJob } from "@/lib/api-client";
import type { ImageGenerationEngine } from "@/lib/generation-engine";

export type ChatFlowStep = 1 | 2 | 3 | 4;

export type EntryMode = "chat_start";

export type ProgressState = {
  current: number;
  total: number;
  label: string;
};

export type InferredContext = {
  businessType: string;
  itemOrService: string;
  promotionGoal: string;
};

export type PartialInferredContext = Partial<InferredContext>;

export type ContextSource = "empty" | "backend" | "sample";

export type OptionItem = {
  id: number | string;
  label: string;
  value: string;
  description?: string | null;
};

export type OptionQuestion = {
  field: string;
  question: string;
  options: OptionItem[];
  required?: boolean;
  multi_select?: boolean;
};

export type ChatTranscriptMessage = {
  role: "user" | "assistant";
  text: string;
};

export type ToneOption = {
  id: string;
  label: string;
  icon: "heart" | "leaf" | "diamond" | "smile" | "sparkles" | "star";
};

export type CopyOption = {
  id: string;
  headline: string;
  subcopy?: string | null;
  cta?: string | null;
  selectedByDefault?: boolean;
};

export type CopyCandidateSource = "empty" | "sample" | "backend";
export type CopyCandidateOrigin = "unknown" | "llm" | "rule_based" | "fallback";
export type CopyGenerationMode = "suggest_candidates" | "auto_pilot" | "custom_input" | "no_copy";

export type CustomCopyFields = {
  userCustomHeadline?: string;
  userCustomSubcopy?: string;
};

export type ChannelOption = {
  id: string;
  label: string;
  ratio: string;
};

export type ChatBrief = {
  purpose: string;
  item: string;
  copy: string;
  tone: string;
  channel: string;
  imageDirection: string;
  finalImagePath?: string | null;
};

export type ReferenceTemplateFields = {
  selectedReferenceTemplateId?: string | null;
  selectedReferenceTemplateTitle?: string | null;
};

export type ReferenceImageFields = {
  referenceImagePath?: string | null;
  referenceImageFile?: File | null;
};

export type ImageGenerationEngineFields = {
  imageGenerationEngine?: ImageGenerationEngine;
};

export type ChatFlowState = {
  entryMode: EntryMode;
  step: ChatFlowStep;
  progress: ProgressState;
  jobId: string;
  threadId: string;
  userInput: string;
  inferredContext: InferredContext;
  contextSource: ContextSource;
  copyCandidates: CopyOption[];
  copyCandidateSource: CopyCandidateSource;
  copyCandidateOrigin: CopyCandidateOrigin;
  copyGenerationMode: CopyGenerationMode;
  selectedTone: string;
  selectedCopyId: string;
  selectedChannelId: string;
  customDirection: string;
  userCustomHeadline: string;
  userCustomSubcopy: string;
  brief: ChatBrief | null;
  generationJob?: GenerationJob | null;
  selectedImageGenerationEngine: ImageGenerationEngine;
  selectedReferenceTemplateId?: string | null;
  selectedReferenceTemplateTitle?: string | null;
  sourceImagePath?: string | null;
  referenceImagePath?: string | null;
  currentQuestion: OptionQuestion | null;
  conversationMessages: ChatTranscriptMessage[];
  isLoading: boolean;
  errorMessage: string | null;
};

export type ChatFlowAction =
  | { type: "reset" }
  | {
      type: "submitPrompt";
      prompt: string;
      copyGenerationMode?: CopyGenerationMode;
      imageGenerationEngine?: ImageGenerationEngine;
      sourceImagePath?: string | null;
      referenceImagePath?: string | null;
      userCustomHeadline?: string | null;
      userCustomSubcopy?: string | null;
      transcriptMode?: "append" | "update_current_turn";
    }
  | {
      type: "backendStartSucceeded";
      prompt: string;
      jobId: string;
      threadId: string;
      context: InferredContext;
      copyCandidates: CopyOption[];
      recommendedCopyId?: string | null;
      copyCandidateSource?: CopyCandidateSource;
      copyCandidateOrigin?: CopyCandidateOrigin;
      copyGenerationMode?: CopyGenerationMode;
      imageGenerationEngine?: ImageGenerationEngine;
      sourceImagePath?: string | null;
      referenceImagePath?: string | null;
      userCustomHeadline?: string | null;
      userCustomSubcopy?: string | null;
    }
  | {
      type: "backendQuestionReceived";
      jobId: string;
      threadId: string;
      context: PartialInferredContext;
      question: OptionQuestion;
      generationJob?: GenerationJob;
      sourceImagePath?: string | null;
      referenceImagePath?: string | null;
    }
  | { type: "submitQuestionAnswer"; label: string }
  | { type: "backendRequestFailed"; message: string }
  | { type: "beginBriefRequest" }
  | { type: "selectTone"; tone: string }
  | { type: "setCopyGenerationMode"; copyGenerationMode: CopyGenerationMode }
  | { type: "setImageGenerationEngine"; imageGenerationEngine: ImageGenerationEngine }
  | { type: "continueToCopy" }
  | { type: "selectCopy"; copyId: string }
  | { type: "selectChannel"; channelId: string }
  | { type: "setCustomDirection"; value: string }
  | { type: "submitBriefRefinement"; message: string; customDirection: string }
  | { type: "backendBriefSucceeded"; brief: ChatBrief }
  | { type: "briefRefinementSucceeded"; brief: ChatBrief }
  | {
      type: "requestContextLoaded";
      selectedReferenceTemplateId?: string | null;
      selectedReferenceTemplateTitle?: string | null;
      draftPrompt?: string | null;
    }
  | {
      type: "referenceTemplateSelected";
      selectedReferenceTemplateId: string;
      selectedReferenceTemplateTitle?: string | null;
    }
  | { type: "referenceTemplateCleared" }
  | { type: "continueToBrief" }
  | {
      type: "restoreThreadSnapshot";
      prompt: string;
      jobId: string;
      threadId: string;
      context: InferredContext;
      copyGenerationMode: CopyGenerationMode;
      copyCandidates: CopyOption[];
      copyCandidateOrigin: CopyCandidateOrigin;
      selectedCopyId: string;
      selectedChannelId: string;
      selectedTone: string;
      selectedImageGenerationEngine: ImageGenerationEngine;
      customDirection: string;
      userCustomHeadline: string;
      userCustomSubcopy: string;
      sourceImagePath: string | null;
      referenceImagePath: string | null;
      selectedReferenceTemplateId: string | null;
      selectedReferenceTemplateTitle: string | null;
      generationJob: GenerationJob;
      currentQuestion: OptionQuestion | null;
      conversationMessages: ChatTranscriptMessage[];
    }
  | { type: "showResultShell" }
  | {
      type: "showGenerationFailure";
      message: string;
      threadId?: string | null;
      userInput?: string | null;
      imageGenerationEngine?: ImageGenerationEngine | null;
    }
  | { type: "back" }
  | { type: "generationJobRequested" }
  | { type: "generationJobUpdated"; generationJob: GenerationJob }
  | {
      type: "generationJobQuestionReceived";
      generationJob: GenerationJob;
      question: OptionQuestion;
      context?: PartialInferredContext;
      sourceImagePath?: string | null;
      referenceImagePath?: string | null;
    }
  | { type: "generationJobInterruptReceived"; generationJob: GenerationJob }
  | { type: "submitGenerationJobAnswer"; label: string }
  | { type: "generationJobFailed"; message: string };
