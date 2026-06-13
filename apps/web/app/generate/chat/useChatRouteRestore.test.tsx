import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useChatRouteRestore } from "./useChatRouteRestore";

describe("useChatRouteRestore", () => {
  it("does not switch to complete while generating route has no job id yet", () => {
    const setGenerationStage = vi.fn();

    renderHook(() =>
      useChatRouteRestore({
        initialStage: "generating",
        jobIdParam: null,
        threadIdParam: null,
        setGenerationStage,
        restoreJob: vi.fn(),
        restoreThread: vi.fn()
      })
    );

    expect(setGenerationStage).not.toHaveBeenCalledWith("complete");
  });
});
