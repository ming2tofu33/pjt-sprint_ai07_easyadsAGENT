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
};

export type ChatFlowState = {
  entryMode: EntryMode;
  step: ChatFlowStep;
  progress: ProgressState;
  jobId: string;
  threadId: string;
  userInput: string;
  inferredContext: InferredContext;
  copyCandidates: CopyOption[];
  selectedTone: string;
  selectedCopyId: string;
  selectedChannelId: string;
  customDirection: string;
  brief: ChatBrief | null;
  isLoading: boolean;
  errorMessage: string | null;
};

export type ChatFlowAction =
  | { type: "submitPrompt"; prompt: string }
  | {
      type: "backendStartSucceeded";
      prompt: string;
      jobId: string;
      threadId: string;
      context: InferredContext;
      copyCandidates: CopyOption[];
      recommendedCopyId?: string | null;
    }
  | { type: "backendRequestFailed"; message: string }
  | { type: "selectTone"; tone: string }
  | { type: "continueToCopy" }
  | { type: "selectCopy"; copyId: string }
  | { type: "selectChannel"; channelId: string }
  | { type: "setCustomDirection"; value: string }
  | { type: "backendBriefSucceeded"; brief: ChatBrief }
  | { type: "continueToBrief" }
  | { type: "back" };
