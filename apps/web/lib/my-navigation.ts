export type MyPageStep = "home" | "account" | "usage" | "settings" | "plan-info";

export function buildMyHref(step: MyPageStep = "home"): string {
  if (step === "home") {
    return "/my";
  }

  if (step === "settings") {
    return "/settings";
  }

  return `/my/${step}`;
}
