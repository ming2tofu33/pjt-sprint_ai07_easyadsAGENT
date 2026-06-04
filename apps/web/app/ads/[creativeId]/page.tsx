import { notFound } from "next/navigation";
import { AdSaveFlowStep } from "@/components/generate/AdSaveFlowStep";
import { MobileShell } from "@/components/generate/MobileShell";
import { archivedCreatives, getAdCreativeById } from "@/lib/mock-dashboard-data";

type AdDetailPageProps = {
  params: {
    creativeId: string;
  };
};

export function generateStaticParams() {
  return archivedCreatives.map((creative) => ({ creativeId: creative.id }));
}

export default function AdDetailPage({ params }: AdDetailPageProps) {
  if (!params.creativeId.startsWith("generated-") && !getAdCreativeById(params.creativeId)) {
    notFound();
  }

  return (
    <MobileShell>
      <AdSaveFlowStep creativeId={params.creativeId} step="detail" />
    </MobileShell>
  );
}
