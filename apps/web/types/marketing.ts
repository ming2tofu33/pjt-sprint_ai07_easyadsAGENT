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
  userInput: string;
  inferredContext: InferredContext;
  selectedTone: string;
  selectedCopyId: string;
  selectedChannelId: string;
  customDirection: string;
};

export type ChatFlowAction =
  | { type: "submitPrompt"; prompt: string }
  | { type: "selectTone"; tone: string }
  | { type: "continueToCopy" }
  | { type: "selectCopy"; copyId: string }
  | { type: "selectChannel"; channelId: string }
  | { type: "setCustomDirection"; value: string }
  | { type: "continueToBrief" }
  | { type: "back" };
