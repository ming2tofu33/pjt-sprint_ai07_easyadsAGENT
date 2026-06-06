import { Suspense } from "react";
import { ChatGenerateClient } from "./chat/ChatGenerateClient";
import type { DashboardStage, DashboardSurface } from "@/lib/dashboard-navigation";

type Props = {
  initialSurface: DashboardSurface;
  initialStage?: DashboardStage;
};

export function ChatGeneratePage({ initialSurface, initialStage }: Props) {
  return (
    <Suspense fallback={null}>
      <ChatGenerateClient initialSurface={initialSurface} initialStage={initialStage} />
    </Suspense>
  );
}
