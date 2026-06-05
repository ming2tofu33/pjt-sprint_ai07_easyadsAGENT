"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";
import styles from "./admin.module.css";

export function AdminSignOutButton() {
  const router = useRouter();
  const [isPending, setIsPending] = useState(false);

  async function handleSignOut() {
    setIsPending(true);
    const supabase = createSupabaseBrowserClient();
    await supabase?.auth.signOut();
    router.replace("/admin/login");
    router.refresh();
  }

  return (
    <button className={styles.signOutButton} type="button" onClick={handleSignOut} disabled={isPending}>
      <LogOut size={15} aria-hidden="true" />
      {isPending ? "로그아웃 중" : "로그아웃"}
    </button>
  );
}
