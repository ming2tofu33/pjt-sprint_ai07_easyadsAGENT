"use client";

import { MessageCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ChatGenerateClient } from "@/app/generate/chat/ChatGenerateClient";
import { MobileShell } from "@/components/generate/MobileShell";
import { ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE } from "@/lib/onboarding-completion";
import styles from "./generate.module.css";

export function HomeEntryClient() {
  const router = useRouter();
  const [canShowHome, setCanShowHome] = useState(false);

  useEffect(() => {
    try {
      if (window.localStorage.getItem(ONBOARDING_COMPLETED_STORAGE_KEY) === ONBOARDING_COMPLETED_VALUE) {
        setCanShowHome(true);
        return;
      }
    } catch {
      setCanShowHome(true);
      return;
    }

    router.replace("/onboarding");
  }, [router]);

  if (!canShowHome) {
    return (
      <MobileShell>
        <section className={styles.homeGate} role="status" aria-live="polite">
          <span className={styles.homeGateMark} aria-hidden="true">
            <MessageCircle size={28} />
          </span>
          <strong>개떡찰떡을 준비하고 있어요</strong>
          <small>처음 방문이면 온보딩으로 안내할게요.</small>
        </section>
      </MobileShell>
    );
  }

  return <ChatGenerateClient initialSurface="home" />;
}
