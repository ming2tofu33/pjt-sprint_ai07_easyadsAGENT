import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("ChatGenerateClient", () => {
  it("walks through the four chat generation steps", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    expect(screen.getByText("대화로 찰떡 만들기")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy();
    fireEvent.click(screen.getByText("상큼한"));
    fireEvent.click(screen.getByText("문구 고르기"));

    expect(screen.getByText("문구와 채널을 골라주세요")).toBeTruthy();
    fireEvent.click(screen.getByText("인스타 스토리"));
    fireEvent.click(screen.getByText("브리프 확인하기"));

    expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy();
    expect(screen.getByText("인스타 스토리 (9:16)")).toBeTruthy();
  });
});
