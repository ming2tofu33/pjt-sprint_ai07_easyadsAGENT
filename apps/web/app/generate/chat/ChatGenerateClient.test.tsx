import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BRAND_KIT_STORAGE_KEY } from "@/lib/brand-kit-storage";

const navigationMock = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn(),
  replace: vi.fn()
}));

vi.mock("@/lib/api-client", () => ({
  startChatGeneration: vi.fn(
    async (
      userInput: string,
      options?: { copyGenerationMode?: string; userCustomHeadline?: string; userCustomSubcopy?: string; selectedReferenceTemplateId?: string }
    ) => {
    if (options?.copyGenerationMode === "no_copy") {
      return {
        type: "brief_ready",
        jobId: "job_no_copy",
        threadId: "thread_no_copy",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "광고 홍보"
        },
        brief: {
          purpose: "광고 홍보",
          item: "딸기라떼",
          copy: "문구 없이 이미지로만",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_no_copy/final_composite.png"
        },
        copyGenerationMode: "no_copy"
      };
    }
    if (options?.copyGenerationMode === "auto_pilot") {
      return {
        type: "brief_ready",
        jobId: "job_auto_pilot",
        threadId: "thread_auto_pilot",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "AI가 고른 딸기라떼 한 잔",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_auto_pilot/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      };
    }
    if (options?.copyGenerationMode === "custom_input") {
      return {
        type: "brief_ready",
        jobId: "job_custom_copy",
        threadId: "thread_custom_copy",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: options.userCustomHeadline ?? "직접 입력한 문구",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_custom_copy/final_composite.png"
        },
        copyGenerationMode: "custom_input"
      };
    }
    if (userInput === "광고 만들어줘") {
      return {
        type: "option_question",
        jobId: "job_question",
        threadId: "thread_question",
        status: "waiting_user_selection",
        context: {},
        question: {
          field: "business_type",
          question: "어떤 업종의 광고인가요?",
          options: [
            { id: 1, label: "음식점/식당", value: "restaurant" },
            { id: 2, label: "카페/디저트", value: "cafe" },
            { id: 9, label: "직접 입력", value: "custom" }
          ]
        },
        missingFields: ["business_type"]
      };
    }

    if (userInput === "후보 없는 광고") {
      return {
        type: "copy_candidates",
        jobId: "job_empty",
        threadId: "thread_empty",
        status: "generating_copy_candidates",
        context: {
          businessType: "카페",
          itemOrService: "대표 메뉴",
          promotionGoal: "광고 홍보"
        },
        copyCandidates: [],
        recommendedCopyId: null
      };
    }

    return {
      type: "copy_candidates",
      jobId: "job_1",
      threadId: "thread_1",
      status: "generating_copy_candidates",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [
        { id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" },
        { id: "copy_2", headline: "오늘만 더 달콤하게, 신메뉴 딸기라떼" }
      ],
      recommendedCopyId: "copy_1"
    };
  }),
  answerChatQuestion: vi.fn(async () => ({
    type: "copy_candidates",
    jobId: "job_question",
    threadId: "thread_question",
    status: "generating_copy_candidates",
    context: {
      businessType: "카페",
      itemOrService: "대표 메뉴",
      promotionGoal: "광고 홍보"
    },
    copyCandidates: [{ id: "copy_1", headline: "우리 가게 대표 메뉴를 알려요" }],
    recommendedCopyId: "copy_1"
  })),
  createChatBrief: vi.fn(async () => ({
    jobId: "job_1",
    threadId: "thread_1",
    status: "done",
    brief: {
      purpose: "신메뉴 출시",
      item: "딸기라떼",
      copy: "봄을 닮은 한 잔, 딸기라떼 출시",
      tone: "상큼한 분위기",
      channel: "인스타 스토리 (9:16)",
      imageDirection: "상큼한 분위기를 살려 딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
      finalImagePath: "data/outputs/job_1/final_composite.png"
    }
  })),
  uploadPhotoAsset: vi.fn(async () => ({
    sourceImagePath: "data/uploads/photo_1.png",
    fileName: "menu.png",
    mimeType: "image/png",
    sizeBytes: 3
  })),
  startPhotoGeneration: vi.fn(async (input?: { copyGenerationMode?: string; userCustomHeadline?: string; userCustomSubcopy?: string }) => {
    if (input?.copyGenerationMode === "no_copy") {
      return {
        type: "brief_ready",
        jobId: "photo_no_copy",
        threadId: "photo_no_copy_thread",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "광고 홍보"
        },
        brief: {
          purpose: "광고 홍보",
          item: "딸기라떼",
          copy: "문구 없이 이미지로만",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/photo_no_copy/final_composite.png"
        },
        copyGenerationMode: "no_copy"
      };
    }
    if (input?.copyGenerationMode === "auto_pilot") {
      return {
        type: "brief_ready",
        jobId: "photo_auto_pilot",
        threadId: "photo_auto_pilot_thread",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "AI가 고른 딸기라떼 한 잔",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/photo_auto_pilot/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      };
    }
    if (input?.copyGenerationMode === "custom_input") {
      return {
        type: "brief_ready",
        jobId: "photo_custom_copy",
        threadId: "photo_custom_copy_thread",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: input.userCustomHeadline ?? "직접 입력한 문구",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/photo_custom_copy/final_composite.png"
        },
        copyGenerationMode: "custom_input"
      };
    }
    return {
      type: "copy_candidates",
      jobId: "photo_1",
      threadId: "photo_1_thread",
      status: "generating_copy_candidates",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
      recommendedCopyId: "copy_photo_1"
    };
  }),
  listReferenceTemplates: vi.fn(async () => ({
    items: [
      {
        templateId: "temp_watermelon_juice_feed",
        title: "수박주스 블루 여름 피드",
        description: "파란 배경과 큼직한 음료 중심의 여름 음료 레퍼런스",
        category: "cafe",
        tags: ["수박", "여름"],
        businessTypes: ["cafe"],
        adFormats: ["instagram_feed"],
        platforms: ["instagram"],
        aspectRatio: "4:3",
        thumbnailUrl: "http://127.0.0.1:4000/api/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
        previewUrl: "http://127.0.0.1:4000/api/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
        styleKeywords: ["summer", "blue"],
        colorPalette: ["#5AB4F2", "#EF3B3B", "#FFFFFF"],
        layoutHint: "top_large_headline_center_product_bottom_copy",
        typographyHint: "extra_bold_condensed_headline",
        popularityScore: 0.5,
        isSaved: false
      }
    ],
    pagination: { limit: 40, offset: 0, total: 1, hasMore: false }
  })),
  saveArchiveItem: vi.fn(async () => ({
    item: {
      adId: "archive_1",
      jobId: "job_1",
      title: "봄을 닮은 한 잔, 딸기라떼 출시",
      imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png",
      thumbnailUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png",
      status: "saved",
      source: "generated",
      metadata: {}
    }
  }))
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: navigationMock.push,
    back: navigationMock.back,
    replace: navigationMock.replace
  })
}));

describe("ChatGenerateClient", () => {
  beforeEach(() => {
    navigationMock.push.mockClear();
    navigationMock.back.mockClear();
    navigationMock.replace.mockClear();
    window.sessionStorage.clear();
  });

  it("walks through the four chat generation steps", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createChatBrief).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    expect(screen.getByText("레퍼런스 보고 만들기")).toBeTruthy();
    fireEvent.click(screen.getByText("대화로 시작하기"));
    expect(screen.getByText("대화로 찰떡 만들기")).toBeTruthy();
    expect(screen.getByLabelText("요청 보내기").hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByText("우리 카페 딸기라떼 신메뉴 광고 만들어줘"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("요청 분석")).toBeTruthy();
    expect(screen.getByText(/요청에 대한 분석 결과/)).toBeTruthy();
    await waitFor(() => expect(screen.getByText("딸기라떼")).toBeTruthy());
    await waitFor(() => expect(screen.getByRole("button", { name: "문구 고르기" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByText("상큼한"));
    fireEvent.click(screen.getByText("문구 고르기"));

    expect(screen.getByText("문구와 채널을 골라주세요")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "AI 추천 문구" })).toBeTruthy();
    expect(screen.getByText("요청 기반")).toBeTruthy();
    expect(screen.queryByText("백엔드 생성")).toBeNull();
    fireEvent.click(screen.getByText("인스타 스토리"));
    fireEvent.click(screen.getByText("브리프 확인하기"));

    await waitFor(() =>
      expect(api.createChatBrief).toHaveBeenCalledWith(
        expect.objectContaining({
          selectedCopyId: "copy_1",
          selectedChannelId: "instagram-story",
          selectedTone: "상큼한",
          customDirection: ""
        })
      )
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("인스타 스토리 (9:16)")).toBeTruthy();

    fireEvent.click(screen.getByText(/생성 결과 확인하기/));
    expect(screen.getByText("이미지 생성이 진행 중이거나 표시할 수 없어요")).toBeTruthy();
    expect(screen.getByText("실제 이미지 파일을 받지 못했어요")).toBeTruthy();
    expect(screen.queryByText("실제 생성")).toBeNull();
    expect(document.querySelector('img[src*="generated-assets"][src*="final_composite.png"]')).toBeNull();

    fireEvent.click(screen.getByText("레퍼런스 갤러리 보기"));
    expect(screen.getByText("찰떡 레퍼런스 둘러보기")).toBeTruthy();
    expect(screen.getByText("결과로 돌아가기")).toBeTruthy();
  });

  it("does not show front-end inferred context while backend analysis is pending", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockReturnValueOnce(new Promise(() => undefined));
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    expect(screen.getAllByText("요청 분석 중").length).toBeGreaterThan(0);
    expect(screen.getByText("분석 중")).toBeTruthy();
    expect(screen.getByText(/분석이 끝난 뒤에만 표시/)).toBeTruthy();
    expect(screen.queryByText("딸기라떼")).toBeNull();
    expect(screen.queryByText("카페")).toBeNull();
    expect(screen.queryByText("신메뉴 출시")).toBeNull();
    expect(screen.getByRole("button", { name: "분석 중..." }).hasAttribute("disabled")).toBe(true);
  });

  it("skips copy selection when chat generation starts in image-only mode", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 이미지만 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("이미지만 생성"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() =>
      expect(api.startChatGeneration).toHaveBeenCalledWith(
        expect.stringContaining("우리 카페 딸기라떼 이미지만 광고 만들어줘"),
        { copyGenerationMode: "no_copy" }
      )
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("문구 없이 이미지로만")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "AI 추천 문구" })).toBeNull();
  });

  it("skips copy selection when chat generation starts in auto-pilot mode", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("AI 자동 완성"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() =>
      expect(api.startChatGeneration).toHaveBeenCalledWith(expect.stringContaining("우리 카페 딸기라떼 신메뉴 광고 만들어줘"), {
        copyGenerationMode: "auto_pilot",
        userCustomHeadline: undefined,
        userCustomSubcopy: undefined
      })
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("AI가 고른 딸기라떼 한 잔")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "AI 추천 문구" })).toBeNull();
  });

  it("skips copy selection when chat generation starts with user-provided copy", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("직접 문구"));
    fireEvent.change(screen.getByLabelText("직접 메인 문구 입력"), {
      target: { value: "오늘만 딸기라떼 반값" }
    });
    fireEvent.change(screen.getByLabelText("직접 보조 문구 입력"), {
      target: { value: "오후 2시부터 5시까지" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() =>
      expect(api.startChatGeneration).toHaveBeenCalledWith(expect.stringContaining("우리 카페 딸기라떼 신메뉴 광고 만들어줘"), {
        copyGenerationMode: "custom_input",
        userCustomHeadline: "오늘만 딸기라떼 반값",
        userCustomSubcopy: "오후 2시부터 5시까지"
      })
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("오늘만 딸기라떼 반값")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "AI 추천 문구" })).toBeNull();
  });

  it("asks a LangGraph option question when the first prompt lacks context", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByRole("heading", { name: "어떤 업종의 광고인가요?" })).toBeTruthy());
    expect(screen.getByText("카페/디저트")).toBeTruthy();

    fireEvent.click(screen.getByText("카페/디저트"));

    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("요청 분석")).toBeTruthy();
    expect(screen.getByText("대표 메뉴")).toBeTruthy();
  });

  it("locks option answers while a LangGraph answer request is pending", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.answerChatQuestion).mockClear();
    vi.mocked(api.answerChatQuestion).mockReturnValueOnce(new Promise(() => undefined));
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    const cafeButton = await screen.findByRole("button", { name: "카페/디저트" });
    fireEvent.click(cafeButton);

    await waitFor(() => expect(cafeButton.hasAttribute("disabled")).toBe(true));
    fireEvent.click(cafeButton);

    expect(api.answerChatQuestion).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("직접 답변 입력").hasAttribute("disabled")).toBe(true);
  });

  it("shows an empty copy state and blocks brief creation when backend candidates are missing", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "후보 없는 광고" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("대표 메뉴")).toBeTruthy());
    await waitFor(() => expect(screen.getByRole("button", { name: "문구 고르기" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByText("문구 고르기"));

    expect(screen.getByRole("heading", { name: "AI 추천 문구" })).toBeTruthy();
    expect(screen.getByText("문구 후보가 아직 없어요")).toBeTruthy();
    expect(screen.queryByText("봄을 닮은 한 잔, 딸기라떼 출시")).toBeNull();
    expect(screen.getByRole("button", { name: "브리프 확인하기" }).hasAttribute("disabled")).toBe(true);
  });

  it("keeps similar style browsing open after generation completes", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByText("대화로 시작하기"));
    fireEvent.click(screen.getByText("우리 카페 딸기라떼 신메뉴 광고 만들어줘"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));
    await waitFor(() => expect(screen.getByText("딸기라떼")).toBeTruthy());
    await waitFor(() => expect(screen.getByRole("button", { name: "문구 고르기" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByText("문구 고르기"));
    expect(screen.getByRole("heading", { name: "AI 추천 문구" })).toBeTruthy();
    fireEvent.click(screen.getByText("브리프 확인하기"));
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());

    fireEvent.click(screen.getByText(/생성 결과 확인하기/));
    expect(screen.getByText("이미지 생성이 진행 중이거나 표시할 수 없어요")).toBeTruthy();
    expect(screen.getByText("실제 이미지 파일을 받지 못했어요")).toBeTruthy();
    expect(screen.queryByText("실제 생성")).toBeNull();
    expect(document.querySelector('img[src*="generated-assets"][src*="final_composite.png"]')).toBeNull();

    fireEvent.click(screen.getByText("레퍼런스 갤러리 보기"));

    expect(screen.getByText("찰떡 레퍼런스 둘러보기")).toBeTruthy();
    expect(screen.getByText("결과로 돌아가기")).toBeTruthy();
    expect(screen.queryByText("이미지 생성이 진행 중이거나 표시할 수 없어요")).toBeNull();
  });

  it("opens the reference gallery from the home dashboard", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listReferenceTemplates).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByText("레퍼런스 보고 만들기"));
    expect(screen.getByText("REFERENCE GALLERY")).toBeTruthy();
    expect(screen.getByText("찰떡 레퍼런스 둘러보기")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "레퍼런스 검색어 입력" }));
    expect(document.activeElement).toBe(screen.getByLabelText("레퍼런스 검색어"));

    fireEvent.click(screen.getByRole("button", { name: "음식" }));
    await waitFor(() =>
      expect(vi.mocked(api.listReferenceTemplates).mock.calls.some(([params]) => params?.category === "food")).toBe(true)
    );

    fireEvent.click(screen.getByLabelText("홈으로"));
    expect(screen.getByText("레퍼런스 보고 만들기")).toBeTruthy();
  });

  it("starts chat generation with a selected reference template", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    await waitFor(() => expect(screen.getByText("수박주스 블루 여름 피드")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "수박주스 블루 여름 피드 스타일로 시작" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat");
    await waitFor(() => expect(screen.getByLabelText("광고 요청 입력")).toBeTruthy());
    const promptInput = screen.getByLabelText("광고 요청 입력") as HTMLTextAreaElement;
    expect(promptInput.value).toBe("");
    expect(screen.getByPlaceholderText("수박주스 블루 여름 피드 스타일을 참고해 어떤 광고를 만들지 적어주세요")).toBeTruthy();

    fireEvent.change(promptInput, { target: { value: "우리 카페 여름 음료 광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(api.startChatGeneration).toHaveBeenCalled());
    expect(vi.mocked(api.startChatGeneration).mock.calls[0][0]).toBe("우리 카페 여름 음료 광고 만들어줘");
    expect(vi.mocked(api.startChatGeneration).mock.calls[0][1]).toMatchObject({
      selectedReferenceTemplateId: "temp_watermelon_juice_feed"
    });
  });

  it("opens the studio entry and dashboard tabs from the home dashboard", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /광고 만들기/ }));
    expect(screen.getByText("어떻게 시작할까요?")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /보관함/ }));
    expect(screen.getByText("내 찰떡 광고")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /마이페이지/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/my");
    expect(screen.getByRole("heading", { name: "마이페이지" })).toBeTruthy();
  });

  it("opens the photo flow from the home dashboard", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /내 사진으로 만들기/ }));

    expect(navigationMock.push).toHaveBeenCalledWith("/generate/photo");
    expect(screen.getByText("내 사진으로 만들기")).toBeTruthy();
    expect(screen.getByText("사진과 광고 방향을 함께 보내주세요.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "사진 선택하기" })).toBeTruthy();
  });

  it("shows a saved brand kit on the home and my page surfaces", async () => {
    window.sessionStorage.setItem(
      BRAND_KIT_STORAGE_KEY,
      JSON.stringify({
        businessName: "연남 테스트 카페",
        businessType: "카페",
        region: "연남동",
        sns: "@test_cafe",
        tones: ["따뜻한"],
        colors: ["#FFD7C9"],
        phrases: ["예약은 DM 주세요"],
        products: ["라떼"],
        status: "saved",
        updatedAt: "2026-06-01T00:00:00.000Z"
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient />);

    await waitFor(() => expect(screen.getByText("브랜드 키트가 연결되어 있어요")).toBeTruthy());
    expect(screen.getByText(/연남 테스트 카페/)).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="my" />);

    await waitFor(() => expect(screen.getByText("브랜드 키트 사용 중")).toBeTruthy());
    expect(screen.getByText(/연남 테스트 카페/)).toBeTruthy();
  });

  it("opens the brand kit start screen from the disconnected my page banner", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="my" />);

    fireEvent.click(screen.getByRole("button", { name: /브랜드 키트 연결 전/ }));

    expect(navigationMock.push).toHaveBeenCalledWith("/brand/kit");
    expect(navigationMock.push).not.toHaveBeenCalledWith("/brand/kit/info");
  });

  it("does not expose an ambiguous see-all menu link on my page", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="my" />);

    expect(screen.queryByRole("button", { name: "전체 보기" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /남은 생성 횟수/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/my/usage");
  });

  it("sends saved brand kit context with chat generation requests", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    window.sessionStorage.setItem(
      BRAND_KIT_STORAGE_KEY,
      JSON.stringify({
        businessName: "연남 테스트 카페",
        businessType: "카페",
        region: "연남동",
        sns: "@test_cafe",
        tones: ["따뜻한"],
        colors: ["#FFD7C9"],
        phrases: ["예약은 DM 주세요"],
        products: ["대표 메뉴"],
        status: "saved",
        updatedAt: "2026-06-01T00:00:00.000Z"
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(api.startChatGeneration).toHaveBeenCalled());
    expect(vi.mocked(api.startChatGeneration).mock.calls[0][0]).toContain("광고 만들어줘");
    expect(vi.mocked(api.startChatGeneration).mock.calls[0][0]).toContain("가게 이름: 연남 테스트 카페");
    expect(vi.mocked(api.startChatGeneration).mock.calls[0][0]).toContain("브랜드 톤: 따뜻한");
  });

  it("renders dashboard surfaces from route props", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient initialSurface="studio" />);
    expect(screen.getByText("어떻게 시작할까요?")).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="reference" />);
    expect(screen.getByText("REFERENCE GALLERY")).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="ads" />);
    expect(screen.getByText("내 찰떡 광고")).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="my" />);
    expect(screen.getByRole("heading", { name: "마이페이지" })).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="brand" />);
    expect(screen.getByRole("heading", { name: "마이페이지" })).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="photo" />);
    expect(screen.getByText("내 사진으로 만들기")).toBeTruthy();
  });

  it("shows an empty generated result state when the complete route has no backend brief", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("생성된 시안이 아직 없어요")).toBeTruthy());
    expect(screen.queryByText("봄을 닮은 한 잔, 딸기라떼 출시")).toBeNull();
    expect(screen.queryByText("카페")).toBeNull();
    expect(screen.queryByText("감성적인")).toBeNull();
    expect(screen.queryByText("인스타 피드")).toBeNull();
    expect(screen.queryByRole("button", { name: /시안 편집하기/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /보관함에서 보기/ })).toBeNull();
  });

  it("restores the backend brief image after the complete route remounts", async () => {
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
        jobId: "job_1",
        threadId: "thread_1",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        copyCandidates: [{ id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" }],
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "감성적인",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔, 딸기라떼 출시",
          tone: "감성적인 카페 무드",
          channel: "인스타 피드 (1:1)",
          imageDirection: "크림톤 배경",
          finalImagePath: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png"
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy());
    expect(screen.getByText("딸기라떼")).toBeTruthy();
    expect(screen.getByRole("button", { name: "딸기라떼 더 크게" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "핑크톤 줄이기" })).toBeNull();
    expect(document.querySelector('img[src*="generated-assets"][src*="final_composite.png"]')).toBeTruthy();
  });

  it("saves a generated result through the archive API before showing success feedback", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.saveArchiveItem).mockClear();
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
        jobId: "job_1",
        threadId: "thread_1",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        copyCandidates: [{ id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" }],
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "감성적인",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔, 딸기라떼 출시",
          tone: "감성적인 카페 무드",
          channel: "인스타 피드 (1:1)",
          imageDirection: "크림톤 배경",
          finalImagePath: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png"
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("봄을 닮은 한 잔, 딸기라떼 출시 저장"));

    await waitFor(() => expect(api.saveArchiveItem).toHaveBeenCalled());
    expect(vi.mocked(api.saveArchiveItem).mock.calls[0][0]).toMatchObject({
      title: "봄을 닮은 한 잔, 딸기라떼 출시",
      publicJobId: "job_1",
      imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png",
      source: "generated"
    });
    expect(screen.getByText("봄을 닮은 한 잔, 딸기라떼 출시를 보관함에 저장했어요.")).toBeTruthy();
  });

  it("opens the session archive from generated results without mock detail routing", async () => {
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
        jobId: "job_1",
        threadId: "thread_1",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        copyCandidates: [{ id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" }],
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "감성적인",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔, 딸기라떼 출시",
          tone: "감성적인 카페 무드",
          channel: "인스타 피드 (1:1)",
          imageDirection: "크림톤 배경",
          finalImagePath: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png"
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy());
    expect(screen.queryByText("New Strawberry Latte")).toBeNull();

    fireEvent.click(screen.getByText("보관함에서 보기"));
    expect(navigationMock.push).toHaveBeenCalledWith("/ads");
  });

  it("opens the selected generated archive item instead of the active complete result", async () => {
    window.sessionStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_latest",
          title: "최근 생성 광고",
          subtitle: "카페 · 인스타 피드",
          format: "1:1",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_latest%2Ffinal_composite.png",
          tone: "strawberry",
          badge: "실제 생성",
          status: "saved",
          channel: "인스타 피드",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["카페", "딸기라떼"]
        },
        {
          id: "generated-job_selected",
          title: "직접 클릭한 생성 광고",
          subtitle: "베이커리 · 포스터",
          format: "4:5",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_selected%2Ffinal_composite.png",
          tone: "cream",
          badge: "실제 생성",
          status: "saved",
          channel: "포스터",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["베이커리", "포스터"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "직접 클릭한 생성 광고 실제 생성 결과 보기" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/ads/generated-job_selected");
    expect(navigationMock.push).not.toHaveBeenCalledWith("/generate/chat/complete");
  });

  it("opens archive search from the header icon and filters generated results", async () => {
    window.sessionStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_latest",
          title: "최근 생성 광고",
          subtitle: "카페 · 인스타 피드",
          format: "1:1",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_latest%2Ffinal_composite.png",
          tone: "strawberry",
          badge: "실제 생성",
          status: "saved",
          channel: "인스타 피드",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "브라우저 임시 보관함",
          savedAt: "방금 생성",
          tags: ["카페", "딸기라떼"]
        },
        {
          id: "generated-job_selected",
          title: "직접 클릭한 생성 광고",
          subtitle: "베이커리 · 포스터",
          format: "4:5",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_selected%2Ffinal_composite.png",
          tone: "cream",
          badge: "실제 생성",
          status: "saved",
          channel: "포스터",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "브라우저 임시 보관함",
          savedAt: "방금 생성",
          tags: ["베이커리", "포스터"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "보관함 검색 열기" }));
    const searchInput = screen.getByLabelText("보관함 검색어") as HTMLInputElement;
    expect(document.activeElement).toBe(searchInput);

    fireEvent.change(searchInput, { target: { value: "베이커리" } });

    expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy();
    expect(screen.queryByText("최근 생성 광고")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "보관함 검색어 지우기" }));
    expect(screen.getByText("최근 생성 광고")).toBeTruthy();
  });

  it("renders the selected generated archive detail from session storage", async () => {
    window.sessionStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_latest",
          title: "최근 생성 광고",
          subtitle: "카페 · 인스타 피드",
          format: "1:1",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_latest%2Ffinal_composite.png",
          tone: "strawberry",
          badge: "실제 생성",
          status: "saved",
          channel: "인스타 피드",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["카페", "딸기라떼"]
        },
        {
          id: "generated-job_selected",
          title: "직접 클릭한 생성 광고",
          subtitle: "베이커리 · 포스터",
          format: "4:5",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_selected%2Ffinal_composite.png",
          tone: "cream",
          badge: "실제 생성",
          status: "saved",
          channel: "포스터",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["베이커리", "포스터"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { AdSaveFlowStep } = await import("@/components/generate/AdSaveFlowStep");

    render(<AdSaveFlowStep creativeId="generated-job_selected" step="detail" />);

    await waitFor(() => expect(screen.getByText("생성 이미지 보기")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy());
    expect(screen.getByText("생성된 이미지만 확인하고 다운로드할 수 있어요.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /이미지 다운로드/ })).toBeTruthy();
    expect(screen.queryByText("최근 생성 광고")).toBeNull();
    expect(screen.queryByText("빠른 수정")).toBeNull();
    expect(screen.queryByRole("button", { name: /이 시안 저장하기/ })).toBeNull();
    expect(document.querySelector('img[src*="job_selected"]')).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /이미지 다운로드/ }));
    expect(screen.getByText("실제 파일 저장 연결 후 다운로드가 활성화돼요.")).toBeTruthy();
  });

  it("shows a mock download action for generated archive items", async () => {
    window.sessionStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_selected",
          title: "직접 클릭한 생성 광고",
          subtitle: "베이커리 · 포스터",
          format: "4:5",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_selected%2Ffinal_composite.png",
          tone: "cream",
          badge: "실제 생성",
          status: "saved",
          channel: "포스터",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["베이커리", "포스터"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "직접 클릭한 생성 광고 더보기" }));

    expect(screen.getByRole("menuitem", { name: "다운로드" })).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: "다운로드" }));

    expect(screen.getByText("직접 클릭한 생성 광고 다운로드는 실제 파일 저장 연결 후 활성화돼요.")).toBeTruthy();
  });

  it("pushes stable URLs when top-level tabs are selected", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /광고 만들기/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/studio");

    fireEvent.click(screen.getAllByRole("button", { name: /레퍼런스/ }).at(-1)!);
    expect(navigationMock.push).toHaveBeenCalledWith("/reference");
  });

  it("opens studio from the empty archive new ad CTA", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    fireEvent.click(screen.getByRole("button", { name: "새 광고 만들기" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/studio");
    expect(navigationMock.push).not.toHaveBeenCalledWith("/generate/chat");
  });

  it("offers previous and home escape routes from chat start", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.click(screen.getByRole("button", { name: "이전 화면" }));
    expect(navigationMock.back).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "홈으로" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/");
  });

  it("shows realistic creative labels in reference cards", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    await waitFor(() => expect(screen.getByText("수박주스 블루 여름 피드")).toBeTruthy());
    expect(screen.getByText("임시 레퍼런스")).toBeTruthy();
    expect(screen.getByText("파란 배경과 큼직한 음료 중심의 여름 음료 레퍼런스")).toBeTruthy();
    expect(screen.queryByText("SPRING SALE")).toBeNull();
  });

  it("shows pending feedback when a reference template save needs real archive storage", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    await waitFor(() => expect(screen.getByText("수박주스 블루 여름 피드")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("수박주스 블루 여름 피드 저장"));

    expect(screen.getByText("수박주스 블루 여름 피드 저장은 실제 보관함 연결 후 사용할 수 있어요.")).toBeTruthy();
    expect(screen.queryByText("수박주스 블루 여름 피드를 보관함에 저장했어요.")).toBeNull();
  });

  it("shows feedback for recent ad and brand kit actions", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient initialSurface="ads" />);

    fireEvent.click(screen.getByRole("button", { name: "보기" }));
    fireEvent.click(screen.getByRole("button", { name: "봄을 닮은 한 잔 다시 보기" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/ads/result-1");

    rerender(<ChatGenerateClient initialSurface="my" />);
    fireEvent.click(screen.getByRole("button", { name: /브랜드 키트 관리/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/brand/kit/info");
  });

  it("opens archive overflow actions and deletes an archive item", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    fireEvent.click(screen.getByRole("button", { name: "보기" }));
    fireEvent.click(screen.getByRole("button", { name: "봄을 닮은 한 잔 더보기" }));

    expect(screen.getByRole("menu", { name: "봄을 닮은 한 잔 작업 메뉴" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "보기" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "비슷하게 만들기" })).toBeTruthy();

    fireEvent.click(screen.getByRole("menuitem", { name: "삭제" }));

    expect(screen.queryByRole("button", { name: "봄을 닮은 한 잔 다시 보기" })).toBeNull();
    expect(screen.getByText("봄을 닮은 한 잔 항목을 보관함에서 삭제했어요.")).toBeTruthy();
  });

  it("opens notifications from home and recent ads headers", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: "알림" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/notifications");

    rerender(<ChatGenerateClient initialSurface="ads" />);
    fireEvent.click(screen.getByRole("button", { name: "알림" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/notifications");
  });

  it("uploads a photo and routes backend generation into the chat flow", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() => expect(api.uploadPhotoAsset).toHaveBeenCalledWith(file));
    await waitFor(() =>
      expect(api.startPhotoGeneration).toHaveBeenCalledWith({
        userInput: "이 사진으로 신메뉴 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png",
        copyGenerationMode: "suggest_candidates"
      })
    );
    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat");
    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("딸기라떼")).toBeTruthy();
    expect(screen.queryByText("AI 분석 결과")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "문구 고르기" }));
    expect(screen.getByText("사진 속 메뉴를 오늘의 신메뉴로")).toBeTruthy();
  });

  it("routes photo generation directly to a backend brief in image-only mode", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 이미지만 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("이미지만 생성"));
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() =>
      expect(api.startPhotoGeneration).toHaveBeenCalledWith({
        userInput: "이 사진으로 이미지만 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png",
        copyGenerationMode: "no_copy"
      })
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("문구 없이 이미지로만")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "AI 추천 문구" })).toBeNull();
  });

  it("routes photo generation directly to a backend brief in auto-pilot mode", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("AI 자동 완성"));
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() =>
      expect(api.startPhotoGeneration).toHaveBeenCalledWith({
        userInput: "이 사진으로 딸기라떼 신메뉴 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png",
        copyGenerationMode: "auto_pilot",
        userCustomHeadline: undefined,
        userCustomSubcopy: undefined
      })
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("AI가 고른 딸기라떼 한 잔")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "AI 추천 문구" })).toBeNull();
  });

  it("routes photo generation directly to a backend brief with user-provided copy", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("직접 문구"));
    fireEvent.change(screen.getByLabelText("사진 직접 메인 문구 입력"), {
      target: { value: "오늘만 딸기라떼 반값" }
    });
    fireEvent.change(screen.getByLabelText("사진 직접 보조 문구 입력"), {
      target: { value: "오후 2시부터 5시까지" }
    });
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() =>
      expect(api.startPhotoGeneration).toHaveBeenCalledWith({
        userInput: "이 사진으로 딸기라떼 신메뉴 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png",
        copyGenerationMode: "custom_input",
        userCustomHeadline: "오늘만 딸기라떼 반값",
        userCustomSubcopy: "오후 2시부터 5시까지"
      })
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("오늘만 딸기라떼 반값")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "AI 추천 문구" })).toBeNull();
  });

  it("sends saved brand kit context with photo generation requests", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    window.sessionStorage.setItem(
      BRAND_KIT_STORAGE_KEY,
      JSON.stringify({
        businessName: "연남 테스트 카페",
        businessType: "카페",
        region: "연남동",
        sns: "@test_cafe",
        tones: ["깔끔한"],
        colors: ["#FFD7C9"],
        phrases: ["예약은 DM 주세요"],
        products: ["대표 메뉴"],
        status: "saved",
        updatedAt: "2026-06-01T00:00:00.000Z"
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 광고 만들어줘" }
    });
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() => expect(api.startPhotoGeneration).toHaveBeenCalled());
    expect(vi.mocked(api.startPhotoGeneration).mock.calls[0][0]).toEqual(
      expect.objectContaining({
        sourceImagePath: "data/uploads/photo_1.png",
        userInput: expect.stringContaining("가게 이름: 연남 테스트 카페")
      })
    );
  });

  it("restores a pending photo turn after the chat route remounts", async () => {
    window.sessionStorage.setItem(
      "easyads_chat_turn_snapshot_v1",
      JSON.stringify({
        prompt: "이 사진으로 신메뉴 광고 만들어줘",
        response: {
          type: "copy_candidates",
          jobId: "photo_1",
          threadId: "photo_1_thread",
          status: "generating_copy_candidates",
          context: {
            businessType: "카페",
            itemOrService: "딸기라떼",
            promotionGoal: "신메뉴 출시"
          },
          copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
          recommendedCopyId: "copy_photo_1"
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("딸기라떼")).toBeTruthy();
    expect(window.sessionStorage.getItem("easyads_chat_turn_snapshot_v1")).not.toBeNull();
  });

  it("keeps a completed photo brief after the chat start route remounts", async () => {
    window.sessionStorage.setItem(
      "easyads_chat_turn_snapshot_v1",
      JSON.stringify({
        prompt: "이 사진으로 신메뉴 광고 만들어줘",
        response: {
          type: "copy_candidates",
          jobId: "photo_1",
          threadId: "photo_1_thread",
          status: "generating_copy_candidates",
          context: {
            businessType: "카페",
            itemOrService: "딸기라떼",
            promotionGoal: "신메뉴 출시"
          },
          copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
          recommendedCopyId: "copy_photo_1"
        }
      })
    );
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "이 사진으로 신메뉴 광고 만들어줘",
        jobId: "photo_1",
        threadId: "photo_1_thread",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
        selectedCopyId: "copy_photo_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "감성적인",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "사진 속 메뉴를 오늘의 신메뉴로",
          tone: "감성적인 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "사진 속 상품이 잘 보이도록 깔끔한 배경과 문구 여백을 구성해요.",
          finalImagePath: null
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("사진 속 메뉴를 오늘의 신메뉴로")).toBeTruthy();
    expect(screen.queryByText("대화로 찰떡 만들기")).toBeNull();
    expect(window.sessionStorage.getItem("easyads_chat_turn_snapshot_v1")).toBeNull();
  });
});
