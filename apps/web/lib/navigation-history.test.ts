import { describe, expect, it, vi } from "vitest";
import { goBackOrPush, shouldUseHistoryBack } from "./navigation-history";

function createRouter() {
  return {
    back: vi.fn(),
    push: vi.fn()
  };
}

describe("navigation history", () => {
  it("uses browser history when a previous page exists", () => {
    const router = createRouter();

    goBackOrPush(router, "/my", 2);

    expect(router.back).toHaveBeenCalledTimes(1);
    expect(router.push).not.toHaveBeenCalled();
  });

  it("uses a fallback href for direct page entry", () => {
    const router = createRouter();

    goBackOrPush(router, "/my", 1);

    expect(router.back).not.toHaveBeenCalled();
    expect(router.push).toHaveBeenCalledWith("/my");
  });

  it("keeps the history threshold explicit", () => {
    expect(shouldUseHistoryBack(0)).toBe(false);
    expect(shouldUseHistoryBack(1)).toBe(false);
    expect(shouldUseHistoryBack(2)).toBe(true);
  });
});
