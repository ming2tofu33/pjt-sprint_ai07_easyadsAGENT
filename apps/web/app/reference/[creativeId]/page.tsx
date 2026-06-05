import { MobileShell } from "@/components/generate/MobileShell";
import { ReferenceStyleFlowStep } from "@/components/generate/ReferenceStyleFlowStep";

type ReferenceDetailPageProps = {
  params: {
    creativeId: string;
  };
};

export default function ReferenceDetailPage({ params }: ReferenceDetailPageProps) {
  return (
    <MobileShell>
      <ReferenceStyleFlowStep creativeId={params.creativeId} step="detail" />
    </MobileShell>
  );
}
