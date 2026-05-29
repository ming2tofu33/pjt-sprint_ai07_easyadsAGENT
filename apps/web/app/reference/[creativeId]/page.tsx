import { notFound } from "next/navigation";
import { MobileShell } from "@/components/generate/MobileShell";
import { ReferenceStyleFlowStep } from "@/components/generate/ReferenceStyleFlowStep";
import { getReferenceCreativeById, referenceCreatives } from "@/lib/mock-dashboard-data";

type ReferenceDetailPageProps = {
  params: {
    creativeId: string;
  };
};

export function generateStaticParams() {
  return referenceCreatives.map((creative) => ({ creativeId: creative.id }));
}

export default function ReferenceDetailPage({ params }: ReferenceDetailPageProps) {
  if (!getReferenceCreativeById(params.creativeId)) {
    notFound();
  }

  return (
    <MobileShell>
      <ReferenceStyleFlowStep creativeId={params.creativeId} step="detail" />
    </MobileShell>
  );
}
