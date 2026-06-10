import { describe, expect, it } from "vitest";
import { archiveItemToCreative } from "./archive-creative";

describe("archiveItemToCreative", () => {
  it("uses downloadUrl when image and thumbnail URLs are absent", () => {
    const creative = archiveItemToCreative({
      adId: "archive_1",
      jobId: "job_1",
      outputId: "output_1",
      title: "DB 저장 광고",
      imageUrl: null,
      thumbnailUrl: null,
      downloadUrl: "https://cdn.example.com/archive_1.png",
      status: "saved",
      adFormat: "1:1",
      platform: "인스타 피드",
      source: "generated",
      storageProvider: "r2",
      mimeType: "image/png",
      width: 1200,
      height: 1200,
      savedAt: "2026-06-05T00:00:00+00:00",
      metadata: { fileName: "archive_1.png", fileType: "PNG", tags: ["카페"] }
    });

    expect(creative?.id).toBe("archive_1");
    expect(creative?.imageUrl).toBe("https://cdn.example.com/archive_1.png");
    expect(creative?.storage).toBe("내 광고 보관함");
  });
});
