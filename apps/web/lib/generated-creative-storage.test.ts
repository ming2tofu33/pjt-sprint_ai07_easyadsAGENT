import { beforeEach, describe, expect, it } from "vitest";
import { addGeneratedCreativeSnapshot, readGeneratedCreatives, removeGeneratedCreative } from "./generated-creative-storage";

describe("generated creative storage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("stores generated chat results as archive creatives", () => {
    const creatives = addGeneratedCreativeSnapshot({
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [{ id: "copy_1", headline: "봄을 닮은 한 잔" }],
      selectedCopyId: "copy_1",
      selectedChannelId: "instagram-feed",
      selectedTone: "감성적인",
      customDirection: "",
      brief: {
        purpose: "신메뉴 출시",
        item: "딸기라떼",
        copy: "봄을 닮은 한 잔",
        tone: "감성적인 분위기",
        channel: "인스타 피드 (1:1)",
        imageDirection: "감성적인 분위기를 살려 딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
        finalImagePath: "data/outputs/job_1/final_composite.png"
      }
    });

    expect(creatives).toHaveLength(1);
    expect(creatives[0].id).toBe("generated-job_1");
    expect(creatives[0].badge).toBe("실제 생성");
    expect(creatives[0].storage).toBe("브라우저 임시 보관함");
    expect(creatives[0].imageUrl).toContain("generated-assets");
    expect(readGeneratedCreatives()[0].title).toBe("봄을 닮은 한 잔");
  });

  it("does not store briefs without a generated image path", () => {
    const creatives = addGeneratedCreativeSnapshot({
      prompt: "이 사진으로 신메뉴 광고 만들어줘",
      jobId: "job_without_image",
      threadId: "thread_without_image",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [{ id: "copy_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
      selectedCopyId: "copy_1",
      selectedChannelId: "instagram-feed",
      selectedTone: "감성적인",
      customDirection: "",
      brief: {
        purpose: "신메뉴 출시",
        item: "딸기라떼",
        copy: "사진 속 메뉴를 오늘의 신메뉴로",
        tone: "감성적인 분위기",
        channel: "인스타 피드 (1:1)",
        imageDirection: "사진 속 상품이 잘 보이도록 구성해요.",
        finalImagePath: null
      }
    });

    expect(creatives).toEqual([]);
    expect(readGeneratedCreatives()).toEqual([]);
  });

  it("removes generated creatives from the session archive", () => {
    addGeneratedCreativeSnapshot({
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [{ id: "copy_1", headline: "봄을 닮은 한 잔" }],
      selectedCopyId: "copy_1",
      selectedChannelId: "instagram-feed",
      selectedTone: "감성적인",
      customDirection: "",
      brief: {
        purpose: "신메뉴 출시",
        item: "딸기라떼",
        copy: "봄을 닮은 한 잔",
        tone: "감성적인 분위기",
        channel: "인스타 피드 (1:1)",
        imageDirection: "감성적인 분위기를 살려 딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
        finalImagePath: "data/outputs/job_1/final_composite.png"
      }
    });

    const nextCreatives = removeGeneratedCreative("generated-job_1");

    expect(nextCreatives).toEqual([]);
    expect(readGeneratedCreatives()).toEqual([]);
  });
});
