import { describe, expect, it } from "vitest";
import { mapChatThreadSnapshotToRestoreState } from "./chat-thread-state-mapper";

describe("mapChatThreadSnapshotToRestoreState", () => {
  it("maps snake_case graph state into UI restore fields", () => {
    const restore = mapChatThreadSnapshotToRestoreState({
      snapshot_id: "snapshot_1",
      thread_id: "thread_1",
      job_id: "job_1",
      snapshot_version: 1,
      schema_version: 1,
      snapshot_kind: "input",
      state_payload: {
        user_input: "오늘 저녁 카페 딸기라떼 할인 광고",
        business_type: "카페",
        item_or_service: "딸기라떼",
        promotion_goal: "할인 이벤트",
        copy_generation_mode: "custom_input",
        user_custom_headline: "오늘만 딸기라떼 반값",
        user_custom_subcopy: "오후 2시부터 5시까지",
        selected_channel_id: "instagram-feed",
        selected_tone: "상큼한",
        image_generation_engine: "gpt_image_2"
      },
      changed_fields: [],
      reference_template_snapshot: {},
      brand_kit_snapshot: {},
      metadata: {},
      created_at: "2026-06-06T00:00:00+00:00"
    });

    expect(restore).toMatchObject({
      prompt: "오늘 저녁 카페 딸기라떼 할인 광고",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "할인 이벤트"
      },
      copyGenerationMode: "custom_input",
      selectedChannelId: "instagram-feed",
      selectedTone: "상큼한",
      selectedImageGenerationEngine: "gpt_image_2",
      userCustomHeadline: "오늘만 딸기라떼 반값",
      userCustomSubcopy: "오후 2시부터 5시까지"
    });
  });

  it("extracts a pending option question from a waiting snapshot", () => {
    const restore = mapChatThreadSnapshotToRestoreState({
      snapshot_id: "snapshot_waiting",
      thread_id: "thread_waiting",
      job_id: "job_waiting",
      snapshot_version: 1,
      schema_version: 1,
      snapshot_kind: "waiting_user_input",
      state_payload: {
        user_input: "광고 만들어줘",
        business_type: "카페",
        pending_interrupt: {
          type: "option_question",
          option_question: {
            field: "item_or_service",
            question: "홍보할 상품이나 서비스는 무엇인가요?",
            options: [{ id: 1, label: "대표 메뉴", value: "signature_item" }]
          }
        }
      },
      changed_fields: [],
      reference_template_snapshot: {},
      brand_kit_snapshot: {},
      metadata: {},
      created_at: "2026-06-06T00:00:00+00:00"
    });

    expect(restore?.generationJob.status).toBe("waiting_user_input");
    expect(restore?.currentQuestion?.field).toBe("item_or_service");
    expect(restore?.currentQuestion?.question).toBe("홍보할 상품이나 서비스는 무엇인가요?");
    expect(restore?.conversationMessages).toEqual([
      { role: "user", text: "광고 만들어줘" },
      { role: "assistant", text: "홍보할 상품이나 서비스는 무엇인가요?" }
    ]);
  });
});
