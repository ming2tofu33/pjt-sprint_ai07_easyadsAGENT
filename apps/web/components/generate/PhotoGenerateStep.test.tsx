import React from "react";
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

function file() {
  return new File(["fake"], "menu.png", { type: "image/png" });
}

describe("PhotoGenerateStep", () => {
  it("shows photo analysis waiting copy while submitting", async () => {
    vi.stubGlobal("React", React);
    const { PhotoGenerateStep } = await import("./PhotoGenerateStep");
    const onGenerate = vi.fn(() => new Promise<void>(() => undefined));
    render(<PhotoGenerateStep onBack={vi.fn()} onGoHome={vi.fn()} onOpenChat={vi.fn()} onGenerate={onGenerate} />);

    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file()] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), { target: { value: "이 사진으로 신메뉴 광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("사진 기반 생성 시작"));

    await waitFor(() => {
      expect(screen.getByText("사용자의 이미지를 분석하는 중이에요")).toBeTruthy();
    });
  });
});
