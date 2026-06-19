export const imageGenerationEngines = ["gpt_image_2", "flux2_klein_4b", "sd35_large"];

const legacyAliases = new Map([
  ["gpt_image_1", "gpt_image_2"],
  ["flux", "flux2_klein_4b"],
  ["flux_schnell", "flux2_klein_4b"],
  ["flux_1_schnell", "flux2_klein_4b"],
  ["flux2_klein", "flux2_klein_4b"]
]);

export function normalizeImageGenerationEngine(value, { allowLegacyAlias = true } = {}) {
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  if (imageGenerationEngines.includes(normalized)) {
    return normalized;
  }
  return allowLegacyAlias ? legacyAliases.get(normalized) : undefined;
}
