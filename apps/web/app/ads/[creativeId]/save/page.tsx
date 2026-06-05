import { AdSaveFlowStep } from "@/components/generate/AdSaveFlowStep";
import { MobileShell } from "@/components/generate/MobileShell";

type AdSavePageProps = {
  params: {
    creativeId: string;
  };
};

export function generateStaticParams() {
  return [];
}

export default function AdSavePage({ params }: AdSavePageProps) {
  return (
    <MobileShell>
      <AdSaveFlowStep creativeId={params.creativeId} step="save" />
    </MobileShell>
  );
}
