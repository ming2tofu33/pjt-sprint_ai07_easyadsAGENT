export const dashboardSurfaces = ["home", "studio", "reference", "ads", "brand", "chat"] as const;
export const dashboardStages = ["start", "brief", "generating", "complete", "similar"] as const;

export type DashboardSurface = (typeof dashboardSurfaces)[number];
export type DashboardStage = (typeof dashboardStages)[number];

const dashboardSurfaceSet = new Set<string>(dashboardSurfaces);
const dashboardStageSet = new Set<string>(dashboardStages);

export function buildDashboardHref(surface: DashboardSurface, stage?: DashboardStage): string {
  const href = `/generate/chat?surface=${surface}`;

  return stage ? `${href}&stage=${stage}` : href;
}

export function parseDashboardSurface(surface: string | null | undefined): DashboardSurface {
  return surface && dashboardSurfaceSet.has(surface) ? (surface as DashboardSurface) : "home";
}

export function parseDashboardStage(stage: string | null | undefined): DashboardStage {
  return stage && dashboardStageSet.has(stage) ? (stage as DashboardStage) : "start";
}
