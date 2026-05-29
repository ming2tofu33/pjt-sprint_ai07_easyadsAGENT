import { MobileShell } from "@/components/generate/MobileShell";
import { NotificationDetailStep } from "@/components/generate/NotificationDetailStep";

export default function FailedNotificationPage() {
  return (
    <MobileShell>
      <NotificationDetailStep variant="failed" />
    </MobileShell>
  );
}
