"use client";

import { LogIn } from "lucide-react";
import { useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";
import styles from "../admin.module.css";

export function AdminLoginClient({ nextPath }: { nextPath: string }) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(false);

  async function handleGoogleLogin() {
    setErrorMessage(null);

    const supabase = createSupabaseBrowserClient();

    if (!supabase) {
      setErrorMessage("로그인 설정이 아직 연결되지 않았어요. 개발 서버를 다시 실행해 주세요.");
      return;
    }

    setIsPending(true);

    const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`;
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo,
        queryParams: {
          access_type: "offline",
          prompt: "consent"
        }
      }
    });

    if (error) {
      setErrorMessage(error.message);
      setIsPending(false);
    }
  }

  return (
    <div>
      <button className={styles.primaryButton} type="button" onClick={handleGoogleLogin} disabled={isPending}>
        <LogIn size={18} aria-hidden="true" />
        {isPending ? "Google로 이동 중" : "Google 계정으로 관리자 로그인"}
      </button>
      {errorMessage ? <p className={styles.errorText}>{errorMessage}</p> : null}
    </div>
  );
}
