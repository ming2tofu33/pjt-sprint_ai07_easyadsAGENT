import { expect, test } from "@playwright/test";
import { ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE } from "../lib/onboarding-completion";

test.beforeEach(async ({ page }, testInfo) => {
  if (testInfo.title.includes("first visit redirects")) {
    return;
  }

  await page.addInitScript(
    ({ key, value }) => {
      window.localStorage.setItem(key, value);
    },
    { key: ONBOARDING_COMPLETED_STORAGE_KEY, value: ONBOARDING_COMPLETED_VALUE }
  );
});

test("first visit redirects to onboarding and stores completion", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: "개떡처럼 말해도, 찰떡같이 광고로." })).toBeVisible();

  await page.getByRole("button", { name: "온보딩 4단계로 이동" }).click();
  await expect(page.getByRole("button", { name: /바로 광고 만들기/ })).toBeVisible();

  await page.getByRole("button", { name: "나중에 할게요" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("레퍼런스 보고 만들기")).toBeVisible();
  const storedValue = await page.evaluate((key) => window.localStorage.getItem(key), ONBOARDING_COMPLETED_STORAGE_KEY);
  expect(storedValue).toBe(ONBOARDING_COMPLETED_VALUE);
});

test("chat start flow reaches final brief on mobile", async ({ page }) => {
  await page.route("**/api/generate/chat/start", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        type: "copy_candidates",
        jobId: "chat_e2e",
        threadId: "chat_e2e_thread",
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
      })
    });
  });
  await page.route("**/api/generate/chat/brief", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        jobId: "chat_e2e",
        threadId: "chat_e2e_thread",
        status: "done",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔, 딸기라떼 출시",
          tone: "상큼한 분위기",
          channel: "인스타 스토리 (9:16)",
          imageDirection: "상큼한 분위기를 살려 딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/chat_e2e/final_composite.png"
        }
      })
    });
  });
  await page.goto("/");

  await expect(page.getByText("레퍼런스 보고 만들기")).toBeVisible();
  await page.getByRole("button", { name: /대화로 시작하기/ }).click();

  await expect(page.getByText("대화로 찰떡 만들기")).toBeVisible();
  await expect(page.getByLabel("요청 보내기")).toBeDisabled();
  await page.getByRole("button", { name: /우리 카페 딸기라떼 신메뉴 광고 만들어줘/ }).click();
  await page.getByLabel("요청 보내기").click();

  await expect(page.getByText("AI가 이렇게 이해했어요")).toBeVisible();
  await page.getByRole("button", { name: /상큼한/ }).click();
  await page.getByRole("button", { name: "문구 고르기" }).click();

  await expect(page.getByText("문구와 채널을 골라주세요")).toBeVisible();
  await page.getByRole("button", { name: /인스타 스토리/ }).click();
  await page.getByRole("button", { name: "브리프 확인하기" }).click();

  await expect(page.getByText("AI가 브리프를 정리했어요")).toBeVisible();
  await expect(page.getByRole("button", { name: /생성 결과 확인하기|결과 상태 확인하기/ })).toBeVisible();

  await page.getByRole("button", { name: /생성 결과 확인하기|결과 상태 확인하기/ }).click();
  await expect(page).toHaveURL(/\/generate\/chat\/complete$/);
  await expect(page.getByRole("heading", { name: "찰떡 광고 시안이 완성됐어요" })).toBeVisible();
});

test("home dashboard opens reference gallery and returns home", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: /레퍼런스 보고 만들기/ }).click();
  await expect(page.getByText("REFERENCE GALLERY")).toBeVisible();
  await expect(page.getByText("찰떡 레퍼런스 둘러보기")).toBeVisible();

  await page.getByLabel("홈으로").click();
  await expect(page.getByText("레퍼런스 보고 만들기")).toBeVisible();
});

test("reference style flow reaches style-based start", async ({ page }) => {
  await page.goto("/reference");

  await page.getByRole("button", { name: "샘플 레퍼런스 보기" }).click();
  await page.getByRole("button", { name: "감성 카페 신메뉴 포스터 상세 보기" }).click();
  await expect(page).toHaveURL(/\/reference\/ref-strawberry-poster$/);
  await expect(page.getByText("레퍼런스 상세")).toBeVisible();

  await page.getByRole("button", { name: /이 스타일로 내 광고 만들기/ }).click();
  await expect(page).toHaveURL(/\/reference\/ref-strawberry-poster\/analysis$/);
  await expect(page.getByText("AI 스타일 분석")).toBeVisible();

  await page.getByRole("button", { name: "비슷한 스타일 더 탐색하기" }).click();
  await expect(page).toHaveURL(/\/reference\/ref-strawberry-poster\/similar$/);
  await expect(page.getByText("비슷한 스타일 추천")).toBeVisible();

  await page.getByRole("button", { name: "이 스타일로 내 광고 만들기" }).click();
  await expect(page).toHaveURL(/\/reference\/ref-strawberry-poster\/start$/);
  await expect(page.getByText("이 스타일로 시작하기")).toBeVisible();
  await expect(page.getByLabel("가게 이름")).toHaveValue("");
  await expect(page.getByRole("button", { name: "다음", exact: true })).toBeDisabled();

  await page.getByRole("button", { name: "카페" }).click();
  await page.getByLabel("가게 이름").fill("연남 테스트 카페");
  await page.getByRole("button", { name: "다음", exact: true }).click();
  await expect(page).toHaveURL(/\/generate\/chat$/);
  await expect(page.getByText("대화로 찰떡 만들기")).toBeVisible();
  await expect(page.getByLabel("광고 요청 입력")).toHaveValue("감성 카페 신메뉴 포스터 스타일로 연남 테스트 카페의 카페 광고를 만들어줘");
});

test("ad save management flow reaches archive", async ({ page }) => {
  await page.goto("/ads/result-1");
  await expect(page).toHaveURL(/\/ads\/result-1$/);
  await expect(page.getByText("찰떡 광고 시안")).toBeVisible();

  await page.getByRole("button", { name: /이 시안 저장하기/ }).click();
  await expect(page).toHaveURL(/\/ads\/result-1\/save$/);
  await expect(page.getByText("광고 저장하기")).toBeVisible();

  await page.getByRole("button", { name: /이미지 저장하기/ }).click();
  await expect(page).toHaveURL(/\/ads\/result-1\/saved$/);
  await expect(page.getByText("광고 이미지가 저장됐어요!")).toBeVisible();

  await page.getByRole("button", { name: "내 광고 보관함 보기" }).click();
  await expect(page).toHaveURL(/\/ads$/);
  await expect(page.getByText("내 찰떡 광고")).toBeVisible();
  await page.getByRole("button", { name: "보기" }).click();
  await expect(page.getByRole("button", { name: "봄을 닮은 한 잔 다시 보기" })).toBeVisible();
});

test("brand kit setup flow reaches completion", async ({ page }) => {
  await page.goto("/my");

  await page.getByRole("button", { name: /브랜드 키트 관리/ }).click();
  await expect(page).toHaveURL(/\/brand\/kit\/info$/);
  await expect(page.getByText("가게 정보를 알려주세요")).toBeVisible();
  await expect(page.getByRole("button", { name: /다음/ })).toBeDisabled();

  await page.getByLabel("가게 이름").fill("연남 테스트 카페");
  await page.getByRole("button", { name: "카페" }).click();
  await page.getByLabel("지역 또는 상권").fill("연남동");
  await page.getByLabel("SNS 계정").fill("@test_cafe");
  await page.getByRole("button", { name: /다음/ }).click();
  await expect(page).toHaveURL(/\/brand\/kit\/tone$/);
  await expect(page.getByText("우리 가게는 어떤 느낌인가요?")).toBeVisible();

  await page.getByRole("button", { name: /따뜻한/ }).click();
  await page.getByRole("button", { name: /예약은 DM 주세요/ }).click();
  await page.getByRole("button", { name: /대표 메뉴/ }).click();
  await page.getByRole("button", { name: /저장하기/ }).click();
  await expect(page).toHaveURL(/\/brand\/kit\/complete$/);
  await expect(page.getByText("브랜드 키트가 저장됐어요")).toBeVisible();
  await expect(page.getByText("연남 테스트 카페")).toBeVisible();
  await expect(page.getByText("카페 · 연남동 · @test_cafe")).toBeVisible();

  await page.goto("/");
  await expect(page.getByText("브랜드 키트가 연결되어 있어요")).toBeVisible();
  await expect(page.getByText(/연남 테스트 카페/)).toBeVisible();

  await page.getByRole("button", { name: /광고 만들기/ }).click();
  await expect(page).toHaveURL(/\/studio$/);
  await expect(page.getByText("어떻게 시작할까요?")).toBeVisible();
});

test("notification flow opens details and settings", async ({ page }) => {
  await page.goto("/notifications");
  await expect(page.getByRole("heading", { name: "알림", exact: true })).toBeVisible();
  await expect(page.getByText("아직 연결된 실제 알림이 없어요")).toBeVisible();

  await page.getByRole("button", { name: "샘플 알림 보기" }).click();
  await page.getByRole("button", { name: "결과 확인하기" }).click();
  await expect(page).toHaveURL(/\/notifications\/complete$/);
  await expect(page.getByRole("heading", { name: "광고 시안이 완성됐어요!" })).toBeVisible();

  await page.goto("/notifications");
  await page.getByRole("button", { name: "샘플 알림 보기" }).click();
  await page.getByRole("button", { name: "다시 시도" }).click();
  await expect(page).toHaveURL(/\/notifications\/failed$/);
  await expect(page.getByRole("heading", { name: "광고 생성에 실패했어요" })).toBeVisible();

  await page.goto("/notifications");
  await page.getByRole("button", { name: "알림 설정" }).click();
  await expect(page).toHaveURL(/\/notifications\/settings$/);
  await expect(page.getByRole("heading", { name: "알림 설정" })).toBeVisible();
});

test("dashboard opens studio, recent ads, and my page tabs", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: /광고 만들기/ }).click();
  await expect(page.getByText("어떻게 시작할까요?")).toBeVisible();

  await page.getByRole("button", { name: /보관함/ }).click();
  await expect(page.getByText("내 찰떡 광고")).toBeVisible();

  await page.getByRole("button", { name: /마이페이지/ }).click();
  await expect(page).toHaveURL(/\/my$/);
  await expect(page.getByRole("heading", { name: "마이페이지" })).toBeVisible();
});

test("my page account usage and settings are directly addressable", async ({ page }) => {
  await page.goto("/my");
  await expect(page.getByRole("heading", { name: "마이페이지" })).toBeVisible();

  await page.goto("/my/account");
  await expect(page.getByRole("heading", { name: "계정 및 가게 정보" })).toBeVisible();

  await page.goto("/my/usage");
  await expect(page.getByRole("heading", { name: "생성 사용량" })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "설정", exact: true })).toBeVisible();
});

test("onboarding flow reaches start choices and studio", async ({ page }) => {
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name: "개떡처럼 말해도, 찰떡같이 광고로." })).toBeVisible();

  await page.getByRole("button", { name: "다음", exact: true }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: "원하는 방식으로 시작하세요" })).toBeVisible();

  await page.getByRole("button", { name: "다음", exact: true }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: "AI가 질문하고 제안해 브리프를 완성해요" })).toBeVisible();

  await page.getByRole("button", { name: "다음" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("button", { name: /바로 광고 만들기/ })).toBeVisible();

  await page.getByRole("button", { name: "온보딩 2단계로 이동" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: "원하는 방식으로 시작하세요" })).toBeVisible();

  await page.getByRole("button", { name: "온보딩 4단계로 이동" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("button", { name: /바로 광고 만들기/ })).toBeVisible();

  await page.getByRole("button", { name: /바로 광고 만들기/ }).click();
  await expect(page).toHaveURL(/\/studio$/);
  await expect(page.getByText("어떻게 시작할까요?")).toBeVisible();
});

test("onboarding inactive slides do not expose focusable controls", async ({ page }) => {
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name: "개떡처럼 말해도, 찰떡같이 광고로." })).toBeVisible();

  const hiddenFocusable = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[aria-hidden="true"]')).flatMap((hiddenRoot) =>
      Array.from(hiddenRoot.querySelectorAll("button, a[href], input, select, textarea, [tabindex]"))
        .filter((node) => node instanceof HTMLElement && !node.hasAttribute("disabled") && node.tabIndex >= 0)
        .map((node) => (node.textContent || node.getAttribute("aria-label") || node.tagName).trim().replace(/\s+/g, " "))
    )
  );

  expect(hiddenFocusable).toEqual([]);

  await page.keyboard.press("Tab");
  await expect(page.locator(":focus-visible")).toBeVisible();
  await expect(page.getByRole("button", { name: "온보딩 1단계로 이동" })).toBeFocused();
});

test("chat start has visible routes back to app navigation", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: /대화로 시작하기/ }).click();
  await expect(page.getByText("대화로 찰떡 만들기")).toBeVisible();

  await page.getByRole("button", { name: "홈으로" }).click();
  await expect(page.getByText("레퍼런스 보고 만들기")).toBeVisible();
});

test("photo upload flow reaches brief and generation", async ({ page }) => {
  await page.route("**/api/generate/photo/upload", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        sourceImagePath: "data/uploads/e2e-photo.png",
        fileName: "menu.png",
        mimeType: "image/png",
        sizeBytes: 67
      })
    });
  });
  await page.route("**/api/generate/photo/start", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        type: "copy_candidates",
        jobId: "photo_e2e",
        threadId: "photo_e2e_thread",
        status: "generating_copy_candidates",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
        recommendedCopyId: "copy_photo_1"
      })
    });
  });
  await page.route("**/api/generate/chat/brief", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        jobId: "photo_e2e",
        threadId: "photo_e2e_thread",
        status: "done",
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
    });
  });
  await page.goto("/");

  await page.getByRole("button", { name: /내 사진으로 만들기/ }).click();
  await expect(page).toHaveURL(/\/generate\/photo$/);
  await expect(page.getByText("사진과 광고 방향을 함께 보내주세요.")).toBeVisible();
  await expect(page.getByRole("button", { name: "사진 선택하기" })).toBeVisible();

  await page.getByLabel("광고 사진 선택").setInputFiles({
    name: "menu.png",
    mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "base64")
  });
  await expect(page.getByRole("button", { name: "다른 사진 선택" })).toBeVisible();
  await page.getByLabel("사진 광고 요청 입력").fill("이 사진으로 신메뉴 광고 만들어줘");
  await page.getByRole("button", { name: /사진 기반 생성 시작/ }).click();

  await expect(page).toHaveURL(/\/generate\/chat$/);
  await expect(page.getByText("AI가 이렇게 이해했어요")).toBeVisible();
  await expect(page.getByText("딸기라떼")).toBeVisible();
  await page.getByRole("button", { name: "문구 고르기" }).click();
  await expect(page.getByText("사진 속 메뉴를 오늘의 신메뉴로")).toBeVisible();
  await page.getByRole("button", { name: "브리프 확인하기" }).click();
  await expect(page.getByText("AI가 브리프를 정리했어요")).toBeVisible();

  await page.reload();
  await expect(page.getByText("AI가 브리프를 정리했어요")).toBeVisible();
  await expect(page.getByText("대화로 찰떡 만들기")).not.toBeVisible();

  await page.getByRole("button", { name: /결과 상태 확인하기/ }).click();
  await expect(page).toHaveURL(/\/generate\/chat\/complete$/);
  await expect(page.getByText("이미지 생성이 완료되지 않았어요")).toBeVisible();
  await expect(page.getByText("실제 이미지 파일을 받지 못했어요")).toBeVisible();
});

test("exception state screens guide recovery actions", async ({ page }) => {
  await page.goto("/reference/empty");
  await expect(page.getByRole("heading", { name: "검색 결과가 없어요" })).toBeVisible();
  await page.getByRole("button", { name: /전체 레퍼런스 보기/ }).click();
  await expect(page).toHaveURL(/\/reference$/);
  await expect(page.getByText("REFERENCE GALLERY")).toBeVisible();

  await page.goto("/ads/empty");
  await expect(page.getByRole("heading", { name: "아직 만든 광고가 없어요" })).toBeVisible();
  await page.getByRole("button", { name: /대화로 시작하기/ }).click();
  await expect(page).toHaveURL(/\/generate\/chat$/);
  await expect(page.getByText("대화로 찰떡 만들기")).toBeVisible();

  await page.goto("/generate/photo/upload-failed");
  await expect(page.getByRole("heading", { name: "사진을 업로드하지 못했어요" })).toBeVisible();
  await page.getByRole("button", { name: /다시 업로드하기/ }).click();
  await expect(page).toHaveURL(/\/generate\/photo$/);
  await expect(page.getByText("사진과 광고 방향을 함께 보내주세요.")).toBeVisible();

  await page.goto("/generate/chat/failed");
  await expect(page.getByRole("heading", { name: "광고 생성에 실패했어요" })).toBeVisible();
  await page.getByRole("button", { name: /브리프 수정하기/ }).click();
  await expect(page).toHaveURL(/\/generate\/chat$/);
  await expect(page.getByText("대화로 찰떡 만들기")).toBeVisible();
});

test("dashboard surfaces are directly addressable", async ({ page }) => {
  test.setTimeout(60000);

  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name: "개떡처럼 말해도, 찰떡같이 광고로." })).toBeVisible();

  await page.goto("/onboarding/modes");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: "개떡처럼 말해도, 찰떡같이 광고로." })).toBeVisible();

  await page.goto("/onboarding/brief");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: "개떡처럼 말해도, 찰떡같이 광고로." })).toBeVisible();

  await page.goto("/onboarding/start");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: "개떡처럼 말해도, 찰떡같이 광고로." })).toBeVisible();

  await page.goto("/studio");
  await expect(page.getByText("어떻게 시작할까요?")).toBeVisible();

  await page.goto("/reference");
  await expect(page.getByText("REFERENCE GALLERY")).toBeVisible();

  await page.goto("/reference/empty");
  await expect(page.getByRole("heading", { name: "검색 결과가 없어요" })).toBeVisible();

  await page.goto("/ads");
  await expect(page.getByText("내 찰떡 광고")).toBeVisible();

  await page.goto("/ads/empty");
  await expect(page.getByRole("heading", { name: "아직 만든 광고가 없어요" })).toBeVisible();

  await page.goto("/ads/result-1");
  await expect(page.getByText("찰떡 광고 시안")).toBeVisible();

  await page.goto("/ads/result-1/save");
  await expect(page.getByText("광고 저장하기")).toBeVisible();

  await page.goto("/ads/result-1/saved");
  await expect(page.getByText("광고 이미지가 저장됐어요!")).toBeVisible();

  await page.goto("/my");
  await expect(page.getByRole("heading", { name: "마이페이지" })).toBeVisible();

  await page.goto("/my/account");
  await expect(page.getByRole("heading", { name: "계정 및 가게 정보" })).toBeVisible();

  await page.goto("/my/usage");
  await expect(page.getByRole("heading", { name: "생성 사용량" })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "설정", exact: true })).toBeVisible();

  await page.goto("/brand");
  await expect(page.getByRole("heading", { name: "마이페이지" })).toBeVisible();

  await page.goto("/brand/kit");
  await expect(page.getByText("우리 가게 정보를 저장해두면,")).toBeVisible();

  await page.goto("/brand/kit/info");
  await expect(page.getByText("가게 정보를 알려주세요")).toBeVisible();

  await page.goto("/brand/kit/tone");
  await expect(page.getByText("우리 가게는 어떤 느낌인가요?")).toBeVisible();

  await page.goto("/brand/kit/complete");
  await expect(page.getByText("브랜드 키트가 아직 저장되지 않았어요")).toBeVisible();

  await page.goto("/notifications");
  await expect(page.getByRole("heading", { name: "알림", exact: true })).toBeVisible();

  await page.goto("/notifications/complete");
  await expect(page.getByRole("heading", { name: "광고 시안이 완성됐어요!" })).toBeVisible();

  await page.goto("/notifications/failed");
  await expect(page.getByRole("heading", { name: "광고 생성에 실패했어요" })).toBeVisible();

  await page.goto("/notifications/settings");
  await expect(page.getByRole("heading", { name: "알림 설정" })).toBeVisible();

  await page.goto("/generate/photo");
  await expect(page.getByText("사진과 광고 방향을 함께 보내주세요.")).toBeVisible();

  await page.goto("/generate/photo/upload-failed");
  await expect(page.getByRole("heading", { name: "사진을 업로드하지 못했어요" })).toBeVisible();

  await page.goto("/generate/chat/failed");
  await expect(page.getByRole("heading", { name: "광고 생성에 실패했어요" })).toBeVisible();

  await page.goto("/generate/chat/complete");
  await expect(page.getByText("생성된 시안이 아직 없어요")).toBeVisible();
});

test("keyboard focus is visible on dashboard controls", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("레퍼런스 보고 만들기")).toBeVisible();

  await page.keyboard.press("Tab");

  await expect(page.locator(":focus-visible")).toBeVisible();
});

test("desktop keeps the app in a centered mobile shell", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium-desktop", "Desktop shell sizing is only meaningful in the desktop project.");

  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/");
  await expect(page.getByText("레퍼런스 보고 만들기")).toBeVisible();

  const shell = page.getByLabel("개떡찰떡 모바일 화면");
  await expect(shell).toBeVisible();

  const box = await shell.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.width).toBeLessThanOrEqual(392);
  expect(box?.height).toBeGreaterThan(700);
});

test("viewport allows mobile zoom", async ({ page }) => {
  await page.goto("/");

  const viewportContent = await page.locator('meta[name="viewport"]').getAttribute("content");

  expect(viewportContent).toContain("width=device-width");
  expect(viewportContent).toContain("initial-scale=1");
  expect(viewportContent).not.toContain("maximum-scale=1");
  expect(viewportContent).not.toContain("user-scalable=no");
});

test("dense mobile routes stay within scroll budget at 390x844", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });

  const routes = ["/ads", "/settings", "/generate/chat/complete"];

  for (const route of routes) {
    await page.goto(route);
    await expect(page.getByLabel("개떡찰떡 모바일 화면")).toBeVisible();

    const metrics = await page.evaluate(() => ({
      scrollHeight: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
      viewportHeight: window.innerHeight,
      overflowX: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth) - window.innerWidth
    }));

    expect(metrics.overflowX).toBeLessThanOrEqual(1);
    expect(metrics.scrollHeight / metrics.viewportHeight).toBeLessThanOrEqual(1.18);
  }
});
