import { ExceptionStateStep } from "@/components/generate/ExceptionStateStep";
import { MobileShell } from "@/components/generate/MobileShell";

export default function PhotoUploadFailedPage() {
  return (
    <MobileShell>
      <ExceptionStateStep kind="uploadFailed" />
    </MobileShell>
  );
}
