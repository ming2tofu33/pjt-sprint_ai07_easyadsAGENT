export type AdSaveStep = "detail" | "save" | "saved";

export function buildAdHref(creativeId: string, step: AdSaveStep = "detail"): string {
  const base = `/ads/${creativeId}`;

  if (step === "detail") {
    return base;
  }

  return `${base}/${step}`;
}
