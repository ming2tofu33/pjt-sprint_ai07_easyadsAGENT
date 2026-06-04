import { BrandKitFlowStep } from "@/components/generate/BrandKitFlowStep";
import { MobileShell } from "@/components/generate/MobileShell";

export default function BrandKitStartPage() {
  return (
    <MobileShell>
      <BrandKitFlowStep step="start" />
    </MobileShell>
  );
}
