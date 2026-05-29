import { ExceptionStateStep } from "@/components/generate/ExceptionStateStep";
import { MobileShell } from "@/components/generate/MobileShell";

export default function ReferenceEmptyPage() {
  return (
    <MobileShell>
      <ExceptionStateStep kind="searchEmpty" />
    </MobileShell>
  );
}
