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
    expect(next.selectedImageGenerationEngine).toBe("gpt_image_1");
  });

  it("clears a thread-limit error code when retrying from the prompt flow", () => {
    const failed = chatFlowReducer(createInitialChatFlowState(), {
      type: "backendRequestFailed",
      message: "작업은 최대 3개까지만 만들 수 있어요.",
      errorCode: "thread_limit_reached"
    });

    const retrying = chatFlowReducer(failed, {
      type: "submitPrompt",
      prompt: "새 광고 요청"
    });

    expect(failed.errorCode).toBe("thread_limit_reached");
    expect(retrying.errorMessage).toBeNull();
    expect(retrying.errorCode).toBeNull();
  });

  it("appends new user prompts and can update the current turn without duplicating it", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "첫 광고 요청"
    });
    state = chatFlowReducer(state, {
      type: "backendQuestionReceived",
      jobId: "job_1",
      threadId: "thread_1",
      context: {},
      question: {
        field: "business_type",
        question: "어떤 업종인가요?",
        options: [{ id: 1, label: "카페", value: "cafe" }]
      }
    });
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "첫 광고 요청 + 참고 이미지",
      referenceImagePath: "r2://references/ref.png",
      transcriptMode: "update_current_turn"
    });
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "두 번째 광고 요청"
    });

    expect(state.conversationMessages).toEqual([
      { role: "user", text: "첫 광고 요청 + 참고 이미지" },
      { role: "assistant", text: "어떤 업종인가요?" },
      { role: "user", text: "두 번째 광고 요청" }
    ]);
  });

  it("does not duplicate the same backend question in the transcript", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "고기집 원육 세일 피드 스타일로 음식점 광고를 만들어줘"
    });
    const question = {
      field: "item_or_service",
      question: "홍보할 상품이나 서비스는 무엇인가요?",
      options: [{ id: 1, label: "대표 메뉴", value: "signature_item" }]
    };
    state = chatFlowReducer(state, {
      type: "backendQuestionReceived",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "음식점/식당",
        promotionGoal: "할인 이벤트"
      },
      question
    });
    state = chatFlowReducer(state, {
      type: "backendQuestionReceived",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "음식점/식당",
        promotionGoal: "할인 이벤트"
      },
      question
    });

    expect(state.conversationMessages).toEqual([
      { role: "user", text: "고기집 원육 세일 피드 스타일로 음식점 광고를 만들어줘" },
      { role: "assistant", text: "홍보할 상품이나 서비스는 무엇인가요?" }
    ]);
  });

  it("does not duplicate the same generation job question in the transcript", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "고기집 원육 세일 피드 스타일로 음식점 광고를 만들어줘"
    });
    const question = {
      field: "item_or_service",
      question: "홍보할 상품이나 서비스는 무엇인가요?",
      options: [{ id: 1, label: "대표 메뉴", value: "signature_item" }]
    };
    state = chatFlowReducer(state, {
      type: "generationJobQuestionReceived",
      generationJob: {
        job_id: "job_1",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "waiting_user_input" }
      },
      question
    });
    state = chatFlowReducer(state, {
      type: "generationJobQuestionReceived",
      generationJob: {
        job_id: "job_1",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "waiting_user_input" }
      },
      question
    });

    expect(state.conversationMessages).toEqual([
      { role: "user", text: "고기집 원육 세일 피드 스타일로 음식점 광고를 만들어줘" },
      { role: "assistant", text: "홍보할 상품이나 서비스는 무엇인가요?" }
    ]);
  });

  it("merges context from a generation job question into the review card", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "고기집 원육 세일 피드 스타일로 고기99 광고를 만들어줘"
    });

    state = chatFlowReducer(state, {
      type: "generationJobQuestionReceived",
      generationJob: {
        job_id: "job_1",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "waiting_user_input" }
      },
      context: {
        businessType: "음식점/식당",
        itemOrService: "원육"
      },
      question: {
        field: "promotion_goal",
        question: "어떤 목적의 광고를 만들까요?",
        options: [{ id: 1, label: "할인 이벤트", value: "discount_event" }]
      }
    });

    expect(state.inferredContext).toEqual({
      businessType: "음식점/식당",
      itemOrService: "원육",
      promotionGoal: ""
    });
    expect(state.contextSource).toBe("backend");
    expect(state.currentQuestion?.field).toBe("promotion_goal");
  });

  it("keeps loading after a generation job answer while the graph continues running", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "광고 만들어줘"
    });
    state = chatFlowReducer(state, {
      type: "generationJobQuestionReceived",
      generationJob: {
        job_id: "job_1",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "waiting_user_input" }
      },
      question: {
        field: "business_type",
        question: "어떤 업종의 광고인가요?",
        options: [{ id: 1, label: "카페/디저트", value: "cafe" }]
      }
    });
    state = chatFlowReducer(state, {
      type: "submitGenerationJobAnswer",
      label: "카페/디저트"
    });
    state = chatFlowReducer(state, {
      type: "generationJobUpdated",
      generationJob: {
        job_id: "job_1",
        status: "running",
        progress: { progress_percent: 60, current_stage: "brief_interpretation" }
      }
    });

    expect(state.currentQuestion).toBeNull();
    expect(state.isLoading).toBe(true);
    expect(state.conversationMessages.at(-1)).toEqual({ role: "user", text: "카페/디저트" });
  });

  it("keeps the selected image generation engine through backend responses", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
      imageGenerationEngine: "flux2_klein_4b"
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

    expect(state.selectedImageGenerationEngine).toBe("flux2_klein_4b");
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
      recommendedCopyId: "copy_backend",
      copyCandidateOrigin: "rule_based"
    });

    expect(state.copyCandidateSource).toBe("backend");
    expect(state.copyCandidateOrigin).toBe("rule_based");
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
    expect(state.copyCandidateOrigin).toBe("unknown");
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

  it("keeps brief refinement requests in the chat transcript", () => {
    const initial = createInitialChatFlowState();
    const refining = chatFlowReducer(initial, {
      type: "submitBriefRefinement",
      message: "상품 사진을 더 크게 보여줘",
      customDirection: "상품 사진을 더 크게 보여줘"
    });
    const refined = chatFlowReducer(refining, {
      type: "briefRefinementSucceeded",
      brief: {
        purpose: "신메뉴 출시",
        item: "딸기라떼",
        copy: "봄을 닮은 한 잔",
        tone: "상큼한 분위기",
        channel: "인스타 피드 (1:1)",
        imageDirection: "상품 사진을 더 크게 보여주는 구성"
      }
    });

    expect(refining.isLoading).toBe(true);
    expect(refining.customDirection).toBe("상품 사진을 더 크게 보여줘");
    expect(refining.conversationMessages.at(-1)).toEqual({ role: "user", text: "상품 사진을 더 크게 보여줘" });
    expect(refined.isLoading).toBe(false);
    expect(refined.brief?.imageDirection).toBe("상품 사진을 더 크게 보여주는 구성");
    expect(refined.conversationMessages.at(-1)).toEqual({
      role: "assistant",
      text: "좋아요. 요청을 반영해서 브리프를 다시 정리했어요."
    });
  });

  it("restores a persisted thread snapshot without losing user context", () => {
    const state = chatFlowReducer(createInitialChatFlowState(), {
      type: "restoreThreadSnapshot",
      prompt: "오늘 저녁 카페 딸기라떼 할인 광고",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "할인 이벤트"
      },
      copyGenerationMode: "custom_input",
      copyCandidates: [],
      copyCandidateOrigin: "unknown",
      selectedCopyId: "",
      selectedChannelId: "instagram-feed",
      selectedTone: "상큼한",
      selectedImageGenerationEngine: "gpt_image_1",
      customDirection: "딸기라떼가 크게 보이게",
      userCustomHeadline: "오늘만 딸기라떼 반값",
      userCustomSubcopy: "오후 2시부터 5시까지",
      sourceImagePath: null,
      referenceImagePath: null,
      selectedReferenceTemplateId: null,
      selectedReferenceTemplateTitle: null,
      generationJob: {
        job_id: "job_1",
        thread_id: "thread_1",
        status: "waiting_user_input"
      },
      currentQuestion: {
        field: "item_or_service",
        question: "홍보할 상품이나 서비스는 무엇인가요?",
        options: [{ id: 1, label: "대표 메뉴", value: "signature_item" }]
      },
      conversationMessages: [
        { role: "user", text: "오늘 저녁 카페 딸기라떼 할인 광고" },
        { role: "assistant", text: "홍보할 상품이나 서비스는 무엇인가요?" }
      ]
    });

    expect(state.step).toBe(4);
    expect(state.jobId).toBe("job_1");
    expect(state.threadId).toBe("thread_1");
    expect(state.userInput).toBe("오늘 저녁 카페 딸기라떼 할인 광고");
    expect(state.inferredContext.itemOrService).toBe("딸기라떼");
    expect(state.copyGenerationMode).toBe("custom_input");
    expect(state.currentQuestion?.field).toBe("item_or_service");
    expect(state.conversationMessages.at(0)?.text).toBe("오늘 저녁 카페 딸기라떼 할인 광고");
  });

  it("restores copy candidates and selected copy from thread snapshots", () => {
    const state = chatFlowReducer(createInitialChatFlowState(), {
      type: "restoreThreadSnapshot",
      prompt: "원육 광고 만들어줘",
      jobId: "job_done",
      threadId: "thread_done",
      context: { businessType: "음식점/식당", itemOrService: "원육", promotionGoal: "리뷰 이벤트" },
      copyGenerationMode: "suggest_candidates",
      copyCandidates: [{ id: "copy_1", headline: "오늘 저녁 원육 한 판" }],
      copyCandidateOrigin: "llm",
      selectedCopyId: "copy_1",
      selectedChannelId: "instagram-feed",
      selectedTone: "bold",
      selectedImageGenerationEngine: "gpt_image_1",
      customDirection: "",
      userCustomHeadline: "",
      userCustomSubcopy: "",
      sourceImagePath: null,
      referenceImagePath: null,
      selectedReferenceTemplateId: null,
      selectedReferenceTemplateTitle: null,
      generationJob: { job_id: "job_done", thread_id: "thread_done", status: "done" },
      currentQuestion: null,
      conversationMessages: [{ role: "user", text: "원육 광고 만들어줘" }]
    });

    expect(state.copyCandidates).toEqual([{ id: "copy_1", headline: "오늘 저녁 원육 한 판" }]);
    expect(state.copyCandidateOrigin).toBe("llm");
    expect(state.selectedCopyId).toBe("copy_1");
  });
});
