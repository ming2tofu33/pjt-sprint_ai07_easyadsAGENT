import { beforeEach, describe, expect, it } from "vitest";

import {
  CHAT_FLOW_BACK_TARGET_STORAGE_KEY,
  CHAT_TURN_SNAPSHOT_STORAGE_KEY,
  clearJsonSnapshot,
  readChatFlowBackTarget,
  readJsonSnapshot,
  writeChatFlowBackTarget,
  writeJsonSnapshot
} from "./chat-snapshots";

beforeEach(() => {
  window.sessionStorage.clear();
});

describe("chat-snapshots", () => {
  it("round-trips JSON snapshots", () => {
    writeJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY, { prompt: "카페 광고", jobId: "job_1" });

    expect(readJsonSnapshot<{ prompt: string; jobId: string }>(CHAT_TURN_SNAPSHOT_STORAGE_KEY)).toEqual({
      prompt: "카페 광고",
      jobId: "job_1"
    });
  });

  it("returns null for corrupted JSON", () => {
    window.sessionStorage.setItem(CHAT_TURN_SNAPSHOT_STORAGE_KEY, "{broken");

    expect(readJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY)).toBeNull();
  });

  it("clears snapshots", () => {
    writeJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY, { prompt: "광고" });
    clearJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY);

    expect(readJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY)).toBeNull();
  });

  it("keeps the chat flow back target in the legacy raw string format", () => {
    writeChatFlowBackTarget("studio");

    expect(window.sessionStorage.getItem(CHAT_FLOW_BACK_TARGET_STORAGE_KEY)).toBe("studio");
    expect(readChatFlowBackTarget()).toBe("studio");
  });

  it("reads existing raw chat flow back targets", () => {
    window.sessionStorage.setItem(CHAT_FLOW_BACK_TARGET_STORAGE_KEY, "reference");

    expect(readChatFlowBackTarget()).toBe("reference");
  });
});
