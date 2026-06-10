import { redirect } from "next/navigation";
import { ADMIN_HOME_PATH, isAdminRole } from "@/lib/admin-auth";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import styles from "../admin.module.css";
import { AdminSignOutButton } from "../AdminSignOutButton";
import { AdminReferenceUploadClient } from "./AdminReferenceUploadClient";

type AdminUserRecord = {
  user_id: string;
  email: string | null;
  role: string;
  active: boolean;
};

export const dynamic = "force-dynamic";

export default async function AdminReferencesPage() {
  const supabase = createSupabaseServerClient();

  if (!supabase) {
    return (
      <main className={styles.page}>
        <section className={styles.phone} aria-label="관리자 설정 필요">
          <div className={styles.body}>
            <section className={styles.config}>
              <h1>관리자 로그인을 연결해야 해요</h1>
              <p className={styles.copy}>Vercel에 `NEXT_PUBLIC_SUPABASE_URL`과 `NEXT_PUBLIC_SUPABASE_ANON_KEY`를 설정해 주세요.</p>
            </section>
          </div>
        </section>
      </main>
    );
  }

  const {
    data: { user },
    error: userError
  } = await supabase.auth.getUser();

  if (userError || !user) {
    redirect(`/admin/login?next=${encodeURIComponent("/admin/references")}`);
  }

  const { data: adminRecord, error: adminError } = await supabase
    .from("admin_users")
    .select("user_id,email,role,active")
    .eq("user_id", user.id)
    .eq("active", true)
    .maybeSingle<AdminUserRecord>();

  if (adminError || !adminRecord || !isAdminRole(adminRecord.role)) {
    redirect(ADMIN_HOME_PATH);
  }

  return (
    <main className={styles.page}>
      <section className={styles.phone} aria-label="레퍼런스 관리">
        <div className={styles.body}>
          <header className={styles.header}>
            <div>
              <p className={styles.eyebrow}>ADMIN</p>
              <h1>샘플 관리</h1>
            </div>
            <AdminSignOutButton />
          </header>
          <AdminReferenceUploadClient />
        </div>
      </section>
    </main>
  );
}
