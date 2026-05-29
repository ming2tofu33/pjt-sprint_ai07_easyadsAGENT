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
  });

  it("builds a complete brief after tone copy and channel selections", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘"
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
    expect(brief.channel).toBe("인스타 피드 (1:1)");
    expect(brief.imageDirection).toContain("크림톤 배경");
  });
});
