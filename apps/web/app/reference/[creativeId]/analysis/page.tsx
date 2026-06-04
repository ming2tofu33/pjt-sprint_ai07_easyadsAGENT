import { MobileShell } from "@/components/generate/MobileShell";
import { ReferenceStyleFlowStep } from "@/components/generate/ReferenceStyleFlowStep";

type ReferenceAnalysisPageProps = {
  params: {
    creativeId: string;
  };
};

export default function ReferenceAnalysisPage({ params }: ReferenceAnalysisPageProps) {
  return (
    <MobileShell>
      <ReferenceStyleFlowStep creativeId={params.creativeId} step="analysis" />
    </MobileShell>
  );
}
