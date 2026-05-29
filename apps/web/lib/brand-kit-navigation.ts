export type BrandKitStep = "start" | "info" | "tone" | "complete";

export function buildBrandKitHref(step: BrandKitStep = "start"): string {
  if (step === "start") {
    return "/brand/kit";
  }

  return `/brand/kit/${step}`;
}
