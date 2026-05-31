import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigationMock = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn(),
  replace: vi.fn()
}));

vi.mock("@/lib/api-client", () => ({
  startChatGeneration: vi.fn(async (userInput: string) => {
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
  startPhotoGeneration: vi.fn(async () => ({
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
    expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy();
    expect(document.querySelector('img[src*="generated-assets"][src*="final_composite.png"]')).toBeTruthy();

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

    fireEvent.click(screen.getByLabelText("요청 보내기"));

    expect(screen.getAllByText("요청 분석 중").length).toBeGreaterThan(0);
    expect(screen.getByText("분석 중")).toBeTruthy();
    expect(screen.getByText(/분석이 끝난 뒤에만 표시/)).toBeTruthy();
    expect(screen.queryByText("딸기라떼")).toBeNull();
    expect(screen.queryByText("카페")).toBeNull();
    expect(screen.queryByText("신메뉴 출시")).toBeNull();
    expect(screen.getByRole("button", { name: "분석 중..." }).hasAttribute("disabled")).toBe(true);
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
    fireEvent.click(screen.getByLabelText("요청 보내기"));
    await waitFor(() => expect(screen.getByText("딸기라떼")).toBeTruthy());
    await waitFor(() => expect(screen.getByRole("button", { name: "문구 고르기" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByText("문구 고르기"));
    expect(screen.getByRole("heading", { name: "AI 추천 문구" })).toBeTruthy();
    fireEvent.click(screen.getByText("브리프 확인하기"));
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());

    fireEvent.click(screen.getByText(/생성 결과 확인하기/));
    expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy();
    expect(document.querySelector('img[src*="generated-assets"][src*="final_composite.png"]')).toBeTruthy();

    fireEvent.click(screen.getByText("레퍼런스 갤러리 보기"));

    expect(screen.getByText("찰떡 레퍼런스 둘러보기")).toBeTruthy();
    expect(screen.getByText("결과로 돌아가기")).toBeTruthy();
    expect(screen.queryByText("찰떡 광고 시안이 완성됐어요")).toBeNull();
  });

  it("opens the reference gallery from the home dashboard", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByText("레퍼런스 보고 만들기"));
    expect(screen.getByText("REFERENCE GALLERY")).toBeTruthy();
    expect(screen.getByText("찰떡 레퍼런스 둘러보기")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("홈으로"));
    expect(screen.getByText("레퍼런스 보고 만들기")).toBeTruthy();
  });

  it("opens a reference style detail from the gallery", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    fireEvent.click(screen.getByRole("button", { name: "샘플 레퍼런스 보기" }));
    fireEvent.click(screen.getByRole("button", { name: "감성 카페 신메뉴 포스터 상세 보기" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/reference/ref-strawberry-poster");
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
    expect(screen.queryByRole("button", { name: /세션 보관함에서 보기/ })).toBeNull();
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
          finalImagePath: "data/outputs/job_1/final_composite.png"
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
          finalImagePath: "data/outputs/job_1/final_composite.png"
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy());
    expect(screen.queryByText("New Strawberry Latte")).toBeNull();

    fireEvent.click(screen.getByText("세션 보관함에서 보기"));
    expect(navigationMock.push).toHaveBeenCalledWith("/ads");
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

    expect(screen.getByText("아직 연결된 레퍼런스 결과가 없어요")).toBeTruthy();
    expect(screen.queryByText("SPRING SALE")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "샘플 레퍼런스 보기" }));

    expect(screen.getByText("SPRING SALE")).toBeTruthy();
    expect(screen.getByText("SUMMER SALE")).toBeTruthy();
  });

  it("shows feedback when a sample reference creative is saved", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    fireEvent.click(screen.getByRole("button", { name: "샘플 레퍼런스 보기" }));
    fireEvent.click(screen.getByLabelText("감성 카페 신메뉴 포스터 저장"));

    expect(screen.getByText("감성 카페 신메뉴 포스터를 보관함에 저장했어요.")).toBeTruthy();
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
        sourceImagePath: "data/uploads/photo_1.png"
      })
    );
    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat");
    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("딸기라떼")).toBeTruthy();
    expect(screen.queryByText("AI 분석 결과")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "문구 고르기" }));
    expect(screen.getByText("사진 속 메뉴를 오늘의 신메뉴로")).toBeTruthy();
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
