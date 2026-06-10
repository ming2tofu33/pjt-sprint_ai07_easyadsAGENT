import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { SmartChatInput } from "./SmartChatInput";

function ControlledSmartChatInput({ onSubmit = vi.fn() }: { onSubmit?: () => void }) {
  const [value, setValue] = useState("");
  return (
    <SmartChatInput
      value={value}
      ariaLabel="광고 요청 입력"
      placeholder="요청을 입력하세요"
      onChange={setValue}
      onSubmit={onSubmit}
      leftControl={<button type="button">첨부</button>}
      rightControl={<button type="button">전송</button>}
    />
  );
}

describe("SmartChatInput", () => {
  it("updates through the change event path used by existing flow tests", () => {
    render(<ControlledSmartChatInput />);

    const input = screen.getByLabelText("광고 요청 입력");
    fireEvent.change(input, { target: { value: "딸기라떼 광고 만들어줘" } });

    expect(input.textContent).toBe("딸기라떼 광고 만들어줘");
  });

  it("submits on Enter", () => {
    const onSubmit = vi.fn();
    render(<ControlledSmartChatInput onSubmit={onSubmit} />);

    fireEvent.keyDown(screen.getByLabelText("광고 요청 입력"), { key: "Enter" });

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("keeps Shift+Enter for multiline editing", () => {
    const onSubmit = vi.fn();
    render(<ControlledSmartChatInput onSubmit={onSubmit} />);

    fireEvent.keyDown(screen.getByLabelText("광고 요청 입력"), { key: "Enter", shiftKey: true });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does not submit while IME composition is active", () => {
    const onSubmit = vi.fn();
    render(<ControlledSmartChatInput onSubmit={onSubmit} />);

    fireEvent.keyDown(screen.getByLabelText("광고 요청 입력"), {
      key: "Enter",
      isComposing: true
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });
});
