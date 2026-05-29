export type OnboardingStep = "intro" | "modes" | "brief" | "start";

export function buildOnboardingHref(_step: OnboardingStep = "intro"): string {
  return "/onboarding";
}
