import { afterEach, describe, expect, it, vi } from "vitest";
import {
  clearGenerationRequestContext,
  readGenerationRequestContext,
  saveGenerationRequestContext
} from "./generation-request-context";

describe("generation request context", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.sessionStorage.clear();
  });

  it("saves, reads, and clears selected reference context", () => {
    saveGenerationRequestContext({
      selectedReferenceTemplateId: "template_1",
      selectedReferenceTemplateTitle: "Cafe style",
      draftPrompt: "Cafe style ad",
      source: "reference_gallery"
    });

    expect(readGenerationRequestContext()).toEqual({
      selectedReferenceTemplateId: "template_1",
      selectedReferenceTemplateTitle: "Cafe style",
      draftPrompt: "Cafe style ad",
      source: "reference_gallery"
    });

    clearGenerationRequestContext();
    expect(readGenerationRequestContext()).toBeNull();
  });

  it("returns null for invalid JSON", () => {
    window.sessionStorage.setItem("easyads_generation_request_context_v1", "{");
    expect(readGenerationRequestContext()).toBeNull();
  });

  it("does not crash when window is unavailable", () => {
    vi.stubGlobal("window", undefined);
    expect(readGenerationRequestContext()).toBeNull();
    expect(() => saveGenerationRequestContext({ selectedReferenceTemplateId: "template_1" })).not.toThrow();
    expect(() => clearGenerationRequestContext()).not.toThrow();
    vi.unstubAllGlobals();
  });
});
