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

export const copyOptions: CopyOption[] = [
  { id: "spring-strawberry", headline: "봄을 닮은 한 잔, 딸기라떼 출시", selectedByDefault: true },
  { id: "today-sweet", headline: "오늘만 더 달콤하게, 신메뉴 딸기라떼" },
  { id: "full-strawberry", headline: "딸기 한가득, 지금 가장 상큼한 메뉴" }
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
    userInput: "",
    inferredContext: {
      businessType: "",
      itemOrService: "",
      promotionGoal: ""
    },
    selectedTone: "감성적인",
    selectedCopyId: "spring-strawberry",
    selectedChannelId: "instagram-feed",
    customDirection: ""
  };
}

export function chatFlowReducer(state: ChatFlowState, action: ChatFlowAction): ChatFlowState {
  switch (action.type) {
    case "submitPrompt":
      return {
        ...state,
        step: 2,
        progress: { current: 1, total: 4, label: "정보 입력" },
        userInput: action.prompt,
        inferredContext: inferContextFromPrompt(action.prompt)
      };
    case "selectTone":
      return {
        ...state,
        selectedTone: action.tone
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
    case "continueToBrief":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "정보 입력" }
      };
    case "back":
      return {
        ...state,
        step: Math.max(1, state.step - 1) as ChatFlowState["step"]
      };
    default:
      return state;
  }
}

export function selectedCopyLabel(state: ChatFlowState): string {
  return copyOptions.find((copy) => copy.id === state.selectedCopyId)?.headline ?? copyOptions[0].headline;
}

export function selectedChannelLabel(state: ChatFlowState): string {
  const channel = channelOptions.find((item) => item.id === state.selectedChannelId) ?? channelOptions[0];
  return `${channel.label} (${channel.ratio})`;
}

export function buildBrief(state: ChatFlowState): ChatBrief {
  return {
    purpose: state.inferredContext.promotionGoal,
    item: state.inferredContext.itemOrService,
    copy: selectedCopyLabel(state),
    tone: `${state.selectedTone}이고 상큼한 카페 무드`,
    channel: selectedChannelLabel(state),
    imageDirection:
      state.customDirection ||
      "크림톤 배경, 딸기라떼를 중앙에 크게 배치하고 우측 여백에 카피 배치"
  };
}
