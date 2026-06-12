import { useEffect, useRef, type MutableRefObject } from "react";

import type { DashboardStage, DashboardSurface } from "@/lib/dashboard-navigation";

export type GenerationStage = "brief" | "generating" | "browsing" | "complete" | "similarBrowsing" | "jobQuestion";

export type UseChatRouteRestoreInput = {
  appSurface?: DashboardSurface;
  initialStage: DashboardStage;
  jobIdParam: string | null;
  threadIdParam: string | null;
  setGenerationStage: (stage: GenerationStage) => void;
  restoreJob: (jobId: string) => void;
  restoreThread: (threadId: string) => void;
  prepareMissingGeneratingRoute?: () => void;
  restoreResources?: boolean;
};

export function isGeneratingRouteWaitingForJob(initialStage: DashboardStage, jobIdParam: string | null): boolean {
  return initialStage === "generating" && !jobIdParam;
}

export function useChatRouteRestore(input: UseChatRouteRestoreInput): MutableRefObject<DashboardStage | null> {
  const lastPrimedStageRef = useRef<DashboardStage | null>(null);
  const {
    appSurface,
    initialStage,
    jobIdParam,
    threadIdParam,
    setGenerationStage,
    restoreJob,
    restoreThread,
    prepareMissingGeneratingRoute,
    restoreResources = false
  } = input;

  useEffect(() => {
    if (appSurface && appSurface !== "chat") {
      lastPrimedStageRef.current = null;
      return;
    }

    if (!isGeneratingRouteWaitingForJob(initialStage, jobIdParam)) {
      return;
    }

    if (lastPrimedStageRef.current === initialStage) {
      return;
    }

    prepareMissingGeneratingRoute?.();
    setGenerationStage("generating");
    lastPrimedStageRef.current = initialStage;
  }, [appSurface, initialStage, jobIdParam, prepareMissingGeneratingRoute, setGenerationStage]);

  useEffect(() => {
    if (!restoreResources || !jobIdParam) {
      return;
    }
    restoreJob(jobIdParam);
  }, [jobIdParam, restoreJob, restoreResources]);

  useEffect(() => {
    if (!restoreResources || !threadIdParam) {
      return;
    }
    restoreThread(threadIdParam);
  }, [restoreResources, restoreThread, threadIdParam]);

  return lastPrimedStageRef;
}
