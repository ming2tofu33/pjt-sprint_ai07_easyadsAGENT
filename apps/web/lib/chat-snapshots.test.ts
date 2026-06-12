import { beforeEach, describe, expect, it } from "vitest";

import {
  CHAT_TURN_SNAPSHOT_STORAGE_KEY,
  clearJsonSnapshot,
  readJsonSnapshot,
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
});
