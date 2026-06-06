import { describe, expect, it } from "vitest";
import {
  buildBrief,
  chatFlowReducer,
  createInitialChatFlowState,
  inferContextFromPrompt
} from "./chat-flow";

describe("chat flow state", () => {
  it("infers cafe strawberry latte launch context from a natural Korean prompt", () => {
    const context = inferContextFromPrompt("우리 카페 딸기라떼 신메뉴 광고 만들어줘");

    expect(context.businessType).toBe("카페");
    expect(context.itemOrService).toBe("딸기라떼");
    expect(context.promotionGoal).toBe("신메뉴 출시");
  });

  it("moves from start to intent review after prompt submit", () => {
    const state = createInitialChatFlowState();
    const next = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘"
    });

    expect(next.step).toBe(2);
    expect(next.userInput).toContain("딸기라떼");
    expect(next.progress.current).toBe(1);
    expect(next.progress.total).toBe(4);
    expect(next.inferredContext).toEqual({
      businessType: "",
      itemOrService: "",
      promotionGoal: ""
    });
    expect(next.contextSource).toBe("empty");
    expect(next.copyCandidateSource).toBe("empty");
    expect(next.selectedImageGenerationEngine).toBe("gpt_image_2");
  });

  it("keeps the selected image generation engine through backend responses", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
      imageGenerationEngine: "flux_schnell"
    });
    state = chatFlowReducer(state, {
      type: "backendStartSucceeded",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [{ id: "copy_backend", headline: "백엔드가 만든 딸기라떼 문구" }],
      recommendedCopyId: "copy_backend"
    });

    expect(state.selectedImageGenerationEngine).toBe("flux_schnell");
  });

  it("marks copy candidates as backend-generated when the backend returns candidates", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘"
    });
    state = chatFlowReducer(state, {
      type: "backendStartSucceeded",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [{ id: "copy_backend", headline: "백엔드가 만든 딸기라떼 문구" }],
      recommendedCopyId: "copy_backend"
    });

    expect(state.copyCandidateSource).toBe("backend");
    expect(state.contextSource).toBe("backend");
    expect(state.copyCandidates[0].headline).toBe("백엔드가 만든 딸기라떼 문구");
    expect(state.selectedCopyId).toBe("copy_backend");
  });

  it("keeps copy candidates empty when the backend returns none", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘"
    });
    state = chatFlowReducer(state, {
      type: "backendStartSucceeded",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [],
      recommendedCopyId: null
    });

    expect(state.copyCandidateSource).toBe("empty");
    expect(state.contextSource).toBe("backend");
    expect(state.copyCandidates).toEqual([]);
    expect(state.selectedCopyId).toBe("");
  });

  it("builds a complete brief after tone copy and channel selections", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘"
    });
    state = chatFlowReducer(state, {
      type: "backendStartSucceeded",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [
        { id: "spring-strawberry", headline: "봄을 닮은 한 잔, 딸기라떼 출시", selectedByDefault: true },
        { id: "today-sweet", headline: "오늘만 더 달콤하게, 신메뉴 딸기라떼" }
      ],
      recommendedCopyId: "spring-strawberry"
    });
    state = chatFlowReducer(state, { type: "selectTone", tone: "감성적인" });
    state = chatFlowReducer(state, { type: "continueToCopy" });
    state = chatFlowReducer(state, {
      type: "selectCopy",
      copyId: "spring-strawberry"
    });
    state = chatFlowReducer(state, {
      type: "selectChannel",
      channelId: "instagram-feed"
    });
    state = chatFlowReducer(state, { type: "continueToBrief" });

    const brief = buildBrief(state);

    expect(state.step).toBe(4);
    expect(brief.purpose).toBe("신메뉴 출시");
    expect(brief.item).toBe("딸기라떼");
    expect(brief.copy).toBe("봄을 닮은 한 잔, 딸기라떼 출시");
    expect(brief.tone).toBe("감성적인 분위기");
    expect(brief.channel).toBe("인스타 피드 (1:1)");
    expect(brief.imageDirection).toBe("감성적인 분위기를 살려 딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.");
    expect(brief.imageDirection).not.toContain("크림톤 배경");
  });

  it("stores a generation job question while preserving the final step", () => {
    const initial = createInitialChatFlowState();
    const state = chatFlowReducer(initial, {
      type: "generationJobQuestionReceived",
      generationJob: {
        job_id: "job_1",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "waiting_user_input" }
      },
      question: {
        field: "business_type",
        question: "어떤 업종인가요?",
        options: [{ id: 1, label: "카페", value: "cafe" }]
      }
    });

    expect(state.step).toBe(4);
    expect(state.currentQuestion?.field).toBe("business_type");
    expect(state.conversationMessages.at(-1)?.text).toBe("어떤 업종인가요?");
    expect(state.isLoading).toBe(false);
  });

  it("marks generation job answer submission as loading", () => {
    const initial = createInitialChatFlowState();
    const asked = chatFlowReducer(initial, {
      type: "generationJobQuestionReceived",
      generationJob: { job_id: "job_1", status: "waiting_user_input" },
      question: {
        field: "business_type",
        question: "어떤 업종인가요?",
        options: [{ id: 1, label: "카페", value: "cafe" }]
      }
    });
    const answered = chatFlowReducer(asked, { type: "submitGenerationJobAnswer", label: "카페" });

    expect(answered.isLoading).toBe(true);
    expect(answered.conversationMessages.at(-1)?.text).toBe("카페");
  });
});
