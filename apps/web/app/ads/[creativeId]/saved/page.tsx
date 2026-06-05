import { AdSaveFlowStep } from "@/components/generate/AdSaveFlowStep";
import { MobileShell } from "@/components/generate/MobileShell";

type AdSavedPageProps = {
  params: {
    creativeId: string;
  };
};

export function generateStaticParams() {
  return [];
}

export default function AdSavedPage({ params }: AdSavedPageProps) {
  return (
    <MobileShell>
      <AdSaveFlowStep creativeId={params.creativeId} step="saved" />
    </MobileShell>
  );
}
