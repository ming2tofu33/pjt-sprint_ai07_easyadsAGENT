import { MobileShell } from "@/components/generate/MobileShell";
import { ReferenceStyleFlowStep } from "@/components/generate/ReferenceStyleFlowStep";

type ReferenceSimilarPageProps = {
  params: {
    creativeId: string;
  };
};

export default function ReferenceSimilarPage({ params }: ReferenceSimilarPageProps) {
  return (
    <MobileShell>
      <ReferenceStyleFlowStep creativeId={params.creativeId} step="similar" />
    </MobileShell>
  );
}
