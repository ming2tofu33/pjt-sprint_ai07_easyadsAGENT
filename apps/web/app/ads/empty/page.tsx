import { ExceptionStateStep } from "@/components/generate/ExceptionStateStep";
import { MobileShell } from "@/components/generate/MobileShell";

export default function AdsEmptyPage() {
  return (
    <MobileShell>
      <ExceptionStateStep kind="archiveEmpty" />
    </MobileShell>
  );
}
