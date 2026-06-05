import { AdSaveFlowStep } from "@/components/generate/AdSaveFlowStep";
import { MobileShell } from "@/components/generate/MobileShell";

type AdDetailPageProps = {
  params: {
    creativeId: string;
  };
};

export function generateStaticParams() {
  return [];
}

export default function AdDetailPage({ params }: AdDetailPageProps) {
  return (
    <MobileShell>
      <AdSaveFlowStep creativeId={params.creativeId} step="detail" />
    </MobileShell>
  );
}
