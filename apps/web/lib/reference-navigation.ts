export type ReferenceStyleStep = "detail" | "analysis" | "similar" | "start";

export function buildReferenceStyleHref(creativeId: string, step: ReferenceStyleStep = "detail"): string {
  const base = `/reference/${creativeId}`;

  if (step === "detail") {
    return base;
  }

  return `${base}/${step}`;
}
