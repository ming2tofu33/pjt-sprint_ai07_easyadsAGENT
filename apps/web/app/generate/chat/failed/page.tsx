import { ExceptionStateStep } from "@/components/generate/ExceptionStateStep";
import { MobileShell } from "@/components/generate/MobileShell";

export default function ChatGenerationFailedPage() {
  return (
    <MobileShell>
      <ExceptionStateStep kind="generationFailed" />
    </MobileShell>
  );
}
