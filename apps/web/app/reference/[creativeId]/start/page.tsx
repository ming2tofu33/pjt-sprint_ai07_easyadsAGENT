import { MobileShell } from "@/components/generate/MobileShell";
import { ReferenceStyleFlowStep } from "@/components/generate/ReferenceStyleFlowStep";

type ReferenceStartPageProps = {
  params: {
    creativeId: string;
  };
};

export default function ReferenceStartPage({ params }: ReferenceStartPageProps) {
  return (
    <MobileShell>
      <ReferenceStyleFlowStep creativeId={params.creativeId} step="start" />
    </MobileShell>
  );
}
