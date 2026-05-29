export const dashboardSurfaces = ["home", "studio", "reference", "ads", "my", "brand", "chat", "photo"] as const;
export const dashboardStages = ["start", "brief", "generating", "complete", "similar"] as const;

export type DashboardSurface = (typeof dashboardSurfaces)[number];
export type DashboardStage = (typeof dashboardStages)[number];

const dashboardSurfaceSet = new Set<string>(dashboardSurfaces);
const dashboardStageSet = new Set<string>(dashboardStages);

export function buildDashboardHref(surface: DashboardSurface, stage?: DashboardStage): string {
  if (surface === "home") {
    return "/";
  }

  if (surface !== "chat") {
    if (surface === "photo") {
      return "/generate/photo";
    }
    if (surface === "my" || surface === "brand") {
      return "/my";
    }
    return `/${surface}`;
  }

  if (!stage || stage === "start" || stage === "brief") {
    return "/generate/chat";
  }

  return `/generate/chat/${stage}`;
}

export function parseDashboardSurface(surface: string | null | undefined): DashboardSurface {
  return surface && dashboardSurfaceSet.has(surface) ? (surface as DashboardSurface) : "home";
}

export function parseDashboardStage(stage: string | null | undefined): DashboardStage {
  return stage && dashboardStageSet.has(stage) ? (stage as DashboardStage) : "start";
}
