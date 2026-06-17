"use client";

import Image from "next/image";
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
          <Image alt="" aria-hidden="true" className={styles.homeGateLogo} height={64} src="/brand/gaetteok-logo.png" width={64} priority />
          <strong>개떡찰떡을 준비하고 있어요</strong>
          <small>처음 방문하셨다면 사용법을 안내해 드릴게요.</small>
        </section>
      </MobileShell>
    );
  }

  return <ChatGenerateClient initialSurface="home" />;
}
