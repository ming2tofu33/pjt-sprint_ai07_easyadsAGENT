const { chromium, expect } = require("@playwright/test");
const fs = require("node:fs/promises");

const WEB_BASE_URL = process.env.QA_WEB_BASE_URL || "http://127.0.0.1:3001";
const BFF_BASE_URL = process.env.QA_BFF_BASE_URL || "http://127.0.0.1:4001";
const onePixelPngBase64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=";

async function createMockJob(label) {
  const response = await fetch(`${BFF_BASE_URL}/api/generation-jobs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      userInput: `${label} 테스트 광고`,
      runMode: "mock_immediate",
      selectedReferenceTemplateId: "temp_watermelon_juice_feed",
      copyGenerationMode: "auto_pilot",
      adFormat: "instagram_feed"
    })
  });
  if (!response.ok) {
    throw new Error(`createMockJob failed: ${response.status} ${await response.text()}`);
  }
  const payload = await response.json();
  const finalImagePath = payload.job && payload.job.result_payload && payload.job.result_payload.final_image_path;
  if (!finalImagePath) {
    throw new Error(`missing final_image_path: ${JSON.stringify(payload)}`);
  }
  return { jobId: payload.job.job_id, finalImagePath };
}

async function newPage(browser) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
  await page.addInitScript(() => {
    window.localStorage.setItem("easyads_onboarding_completed", "true");
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      console.error(`[browser:${message.type()}] ${message.text()}`);
    }
  });
  return page;
}

async function runReferenceSelectionSmoke(browser) {
  const page = await newPage(browser);
  await page.goto(`${WEB_BASE_URL}/reference`, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "찰떡 광고 샘플 둘러보기" })).toBeVisible({ timeout: 10000 });
  const title = "수박주스 블루 여름 피드";
  await page.getByRole("button", { name: `${title} 스타일로 시작` }).scrollIntoViewIfNeeded();
  await page.getByRole("button", { name: `${title} 스타일로 시작` }).click();
  await expect(page.getByLabel("광고 요청 입력")).toHaveValue(`${title} 스타일로 광고 만들어줘`, { timeout: 10000 });
  const requestPromise = page.waitForRequest((request) => request.method() === "POST" && request.url().includes("/api/generate/chat/start"));
  await page.getByLabel("요청 보내기").click();
  const request = await requestPromise;
  const body = JSON.parse(request.postData() || "{}");
  await page.screenshot({ path: "/tmp/easyads-reference-selection-smoke.png", fullPage: true });
  await page.close();
  if (body.selectedReferenceTemplateId !== "temp_watermelon_juice_feed") {
    throw new Error(`reference template id was not forwarded: ${JSON.stringify(body)}`);
  }
  return { status: "PASS", selectedReferenceTemplateId: body.selectedReferenceTemplateId, prompt: body.userInput };
}

async function runPhotoUploadSmoke(browser) {
  await fs.writeFile("/tmp/easyads-photo-upload-input.png", Buffer.from(onePixelPngBase64, "base64"));
  const page = await newPage(browser);
  await page.goto(`${WEB_BASE_URL}/generate/photo`, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "내 사진으로 만들기" })).toBeVisible({ timeout: 10000 });
  await page.getByLabel("광고 사진 선택").setInputFiles({
    name: "smoke-menu.png",
    mimeType: "image/png",
    buffer: Buffer.from(onePixelPngBase64, "base64")
  });
  await expect(page.getByText("사진이 선택됐어요")).toBeVisible({ timeout: 10000 });
  await page.getByLabel("사진 광고 요청 입력").fill("이 사진으로 카페 수박주스 신메뉴 인스타 광고 만들어줘");
  const uploadResponsePromise = page.waitForResponse(
    (response) => response.url().includes("/api/assets/uploads/") && response.url().endsWith("/complete") && response.status() === 200
  );
  const startRequestPromise = page.waitForRequest(
    (request) => request.method() === "POST" && request.url().includes("/api/generation-jobs")
  );
  await page.getByRole("button", { name: /사진 기반 생성 시작/ }).click();
  const uploadResponse = await uploadResponsePromise;
  const uploadPayload = await uploadResponse.json();
  const startRequest = await startRequestPromise;
  const startBody = JSON.parse(startRequest.postData() || "{}");
  await page.screenshot({ path: "/tmp/easyads-photo-upload-smoke.png", fullPage: true });
  await page.close();
  const sourceAssetId = uploadPayload.asset?.assetId ?? uploadPayload.asset?.asset_id;
  if (!sourceAssetId) {
    throw new Error(`upload did not return a public asset id: ${JSON.stringify(uploadPayload)}`);
  }
  if (startBody.sourceAssetId !== sourceAssetId) {
    throw new Error(`generation job did not use uploaded source asset id: ${JSON.stringify({ uploadPayload, startBody })}`);
  }
  return { status: "PASS", sourceAssetId: startBody.sourceAssetId, prompt: startBody.userInput };
}

async function runArchiveSelectedItemSmoke(browser) {
  const latest = await createMockJob("최근 항목");
  const selected = await createMockJob("클릭 항목");
  const selectedTitle = "클릭한 수박주스 광고";
  const latestTitle = "최근 생성한 라떼 광고";
  const page = await newPage(browser);
  await page.addInitScript(({ latest, selected, latestTitle, selectedTitle }) => {
    window.sessionStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_latest",
          title: latestTitle,
          subtitle: "라떼 · 인스타 피드 (1:1)",
          format: "1:1",
          imageUrl: `/api/generated-assets?path=${encodeURIComponent(latest.finalImagePath)}`,
          date: "방금 생성",
          tone: "strawberry",
          badge: "실제 생성",
          status: "saved",
          channel: "인스타 피드",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "세션 보관함",
          savedAt: "방금 생성",
          tags: ["카페", "라떼", "신메뉴"]
        },
        {
          id: "generated-job_selected",
          title: selectedTitle,
          subtitle: "수박주스 · 인스타 피드 (1:1)",
          format: "1:1",
          imageUrl: `/api/generated-assets?path=${encodeURIComponent(selected.finalImagePath)}`,
          date: "방금 생성",
          tone: "mint",
          badge: "실제 생성",
          status: "saved",
          channel: "인스타 피드",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "세션 보관함",
          savedAt: "방금 생성",
          tags: ["카페", "수박주스", "신메뉴"]
        }
      ])
    );
  }, { latest, selected, latestTitle, selectedTitle });
  await page.goto(`${WEB_BASE_URL}/ads`, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "내 찰떡 광고" })).toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: `${selectedTitle} 실제 생성 결과 보기` }).click();
  await expect(page).toHaveURL(/\/ads\/generated-job_selected/);
  await expect(page.getByRole("heading", { name: selectedTitle })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("heading", { name: latestTitle })).toHaveCount(0);
  await page.screenshot({ path: "/tmp/easyads-archive-selected-smoke.png", fullPage: true });
  await page.close();
  return { status: "PASS", openedPath: "/ads/generated-job_selected", selectedTitle };
}

async function runCompleteImageSmoke(browser) {
  const job = await createMockJob("완료 화면");
  const assetResponse = await fetch(`${WEB_BASE_URL}/api/generated-assets?path=${encodeURIComponent(job.finalImagePath)}`);
  const page = await newPage(browser);
  await page.addInitScript(({ finalImagePath }) => {
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "완료 화면 이미지 테스트",
        jobId: "ui_image_smoke",
        threadId: "ui_image_smoke_thread",
        context: { businessType: "카페", itemOrService: "수박주스", promotionGoal: "신메뉴 출시" },
        copyCandidates: [{ id: "copy_1", headline: "시원한 수박주스 한 잔" }],
        copyCandidateSource: "backend",
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "상큼한",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "수박주스",
          copy: "시원한 수박주스 한 잔",
          tone: "상큼한 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "수박주스 중심의 테스트 이미지",
          finalImagePath
        },
        selectedReferenceTemplateId: "temp_watermelon_juice_feed",
        selectedReferenceTemplateTitle: "수박주스 블루 여름 피드"
      })
    );
  }, { finalImagePath: job.finalImagePath });
  await page.goto(`${WEB_BASE_URL}/generate/chat/complete`, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "찰떡 광고 시안이 완성됐어요" })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("실제 생성", { exact: true })).toBeVisible();
  const imageSrc = await page.locator('img[src*="generated-assets"]').first().getAttribute("src");
  await page.screenshot({ path: "/tmp/easyads-complete-image-smoke.png", fullPage: true });
  await page.close();
  if (!assetResponse.ok) {
    throw new Error(`generated asset route failed: ${assetResponse.status}`);
  }
  if (!imageSrc || !imageSrc.includes("generated-assets")) {
    throw new Error(`complete page did not render generated asset image: ${imageSrc}`);
  }
  return { status: "PASS", finalImagePath: job.finalImagePath, assetStatus: assetResponse.status, imageSrc };
}

async function runMissingImageFallbackSmoke(browser) {
  const page = await newPage(browser);
  await page.addInitScript(() => {
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "이미지 없는 완료 화면 테스트",
        jobId: "ui_empty_image_smoke",
        threadId: "ui_empty_image_smoke_thread",
        context: { businessType: "카페", itemOrService: "수박주스", promotionGoal: "신메뉴 출시" },
        copyCandidates: [{ id: "copy_1", headline: "시원한 수박주스 한 잔" }],
        copyCandidateSource: "backend",
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "상큼한",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "수박주스",
          copy: "시원한 수박주스 한 잔",
          tone: "상큼한 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "수박주스 중심의 테스트 이미지",
          finalImagePath: null
        }
      })
    );
  });
  await page.goto(`${WEB_BASE_URL}/generate/chat/complete`, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "이미지 생성이 완료되지 않았어요" })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("실제 이미지 파일을 받지 못했어요")).toBeVisible();
  const generatedImgCount = await page.locator('img[src*="generated-assets"]').count();
  await page.screenshot({ path: "/tmp/easyads-missing-image-smoke.png", fullPage: true });
  await page.close();
  if (generatedImgCount !== 0) {
    throw new Error(`missing image state still rendered generated asset images: ${generatedImgCount}`);
  }
  return { status: "PASS", generatedImgCount };
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const results = {};
  try {
    results.referenceSelection = await runReferenceSelectionSmoke(browser);
    results.photoUpload = await runPhotoUploadSmoke(browser);
    results.archiveSelectedItem = await runArchiveSelectedItemSmoke(browser);
    results.completeImage = await runCompleteImageSmoke(browser);
    results.missingImageFallback = await runMissingImageFallbackSmoke(browser);
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(results, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
