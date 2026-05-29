export type NotificationStep = "center" | "complete" | "failed" | "settings";

export function buildNotificationHref(step: NotificationStep = "center"): string {
  if (step === "center") {
    return "/notifications";
  }

  return `/notifications/${step}`;
}
