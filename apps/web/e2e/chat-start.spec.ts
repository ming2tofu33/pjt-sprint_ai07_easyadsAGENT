import { expect, test } from "@playwright/test";

test("chat start flow reaches final brief on mobile", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("레퍼런스 보고 만들기")).toBeVisible();
  await page.getByRole("button", { name: /대화로 시작하기/ }).click();

  await expect(page.getByText("대화로 찰떡 만들기")).toBeVisible();
  await page.getByLabel("요청 보내기").click();

  await expect(page.getByText("AI가 이렇게 이해했어요")).toBeVisible();
  await page.getByRole("button", { name: /상큼한/ }).click();
  await page.getByRole("button", { name: "문구 고르기" }).click();

  await expect(page.getByText("문구와 채널을 골라주세요")).toBeVisible();
  await page.getByRole("button", { name: /인스타 스토리/ }).click();
  await page.getByRole("button", { name: "브리프 확인하기" }).click();

  await expect(page.getByText("AI가 브리프를 정리했어요")).toBeVisible();
  await expect(page.getByText("찰떡 광고 생성하기")).toBeVisible();

  await page.getByRole("button", { name: /찰떡 광고 생성하기/ }).click();
  await expect(page.getByText("찰떡 광고를 만들고 있어요")).toBeVisible();

  await page.getByRole("button", { name: "기다리는 동안 둘러보기" }).click();
  await expect(page.getByText("찰떡 레퍼런스 둘러보기")).toBeVisible();
  await expect(page.getByRole("button", { name: "진행 상황 보기" })).toBeVisible();
});

test("home mock hub opens reference gallery and returns home", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: /레퍼런스 보고 만들기/ }).click();
  await expect(page.getByText("REFERENCE GALLERY")).toBeVisible();
  await expect(page.getByText("찰떡 레퍼런스 둘러보기")).toBeVisible();

  await page.getByLabel("홈으로").click();
  await expect(page.getByText("레퍼런스 보고 만들기")).toBeVisible();
});

test("dashboard opens studio, recent ads, and brand kit tabs", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: /광고 만들기/ }).click();
  await expect(page.getByText("어떻게 시작할까요?")).toBeVisible();

  await page.getByRole("button", { name: /보관함/ }).click();
  await expect(page.getByText("내 찰떡 광고")).toBeVisible();

  await page.getByRole("button", { name: /마이페이지/ }).click();
  await expect(page.getByText("추천 & 브랜드 키트")).toBeVisible();
});

test("chat start has visible routes back to app navigation", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: /대화로 시작하기/ }).click();
  await expect(page.getByText("대화로 찰떡 만들기")).toBeVisible();

  await page.getByRole("button", { name: "홈으로" }).click();
  await expect(page.getByText("레퍼런스 보고 만들기")).toBeVisible();
});

test("dashboard surfaces are directly addressable", async ({ page }) => {
  await page.goto("/studio");
  await expect(page.getByText("어떻게 시작할까요?")).toBeVisible();

  await page.goto("/reference");
  await expect(page.getByText("REFERENCE GALLERY")).toBeVisible();

  await page.goto("/ads");
  await expect(page.getByText("내 찰떡 광고")).toBeVisible();

  await page.goto("/brand");
  await expect(page.getByText("추천 & 브랜드 키트")).toBeVisible();

  await page.goto("/generate/chat/complete");
  await expect(page.getByText("찰떡 광고 시안이 완성됐어요")).toBeVisible();
});

test("keyboard focus is visible on dashboard controls", async ({ page }) => {
  await page.goto("/");

  await page.keyboard.press("Tab");

  await expect(page.locator(":focus-visible")).toBeVisible();
});

test("desktop keeps the app in a centered mobile shell", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/");

  const shell = page.getByLabel("개떡찰떡 모바일 화면");
  await expect(shell).toBeVisible();

  const box = await shell.boundingBox();
  expect(box?.width).toBeLessThanOrEqual(392);
  expect(box?.height).toBeGreaterThan(700);
});
