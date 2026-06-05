import { redirect } from "next/navigation";
import { ADMIN_HOME_PATH, isAdminRole } from "@/lib/admin-auth";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import styles from "./admin.module.css";
import { AdminHome } from "./AdminHome";
import { AdminSignOutButton } from "./AdminSignOutButton";

type AdminUserRecord = {
  user_id: string;
  email: string | null;
  role: string;
  active: boolean;
};

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const supabase = createSupabaseServerClient();

  if (!supabase) {
    return (
      <main className={styles.page}>
        <section className={styles.phone} aria-label="관리자 설정 필요">
          <div className={styles.body}>
            <section className={styles.config}>
              <h1>관리자 로그인을 연결해야 해요</h1>
              <p className={styles.copy}>Vercel에 `NEXT_PUBLIC_SUPABASE_URL`과 `NEXT_PUBLIC_SUPABASE_ANON_KEY`를 설정하면 Google 로그인을 사용할 수 있습니다.</p>
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
    redirect(`/admin/login?next=${encodeURIComponent(ADMIN_HOME_PATH)}`);
  }

  const { data: adminRecord, error: adminError } = await supabase
    .from("admin_users")
    .select("user_id,email,role,active")
    .eq("user_id", user.id)
    .eq("active", true)
    .maybeSingle<AdminUserRecord>();

  if (adminError) {
    return (
      <main className={styles.page}>
        <section className={styles.phone} aria-label="관리자 권한 테이블 확인 실패">
          <div className={styles.body}>
            <header className={styles.header}>
              <div>
                <p className={styles.eyebrow}>ADMIN</p>
                <h1>권한 테이블 확인 필요</h1>
              </div>
              <AdminSignOutButton />
            </header>

            <section className={styles.config}>
              <h2>관리자 권한 정보를 불러오지 못했어요.</h2>
              <p className={styles.copy}>Supabase에 `admin_users` 마이그레이션이 적용되어 있는지 확인해 주세요.</p>
              <pre className={styles.codeBox}>{adminError.message}</pre>
            </section>
          </div>
        </section>
      </main>
    );
  }

  if (!adminRecord || !isAdminRole(adminRecord.role)) {
    return (
      <main className={styles.page}>
        <section className={styles.phone} aria-label="관리자 권한 없음">
          <div className={styles.body}>
            <header className={styles.header}>
              <div>
                <p className={styles.eyebrow}>ADMIN</p>
                <h1>권한 확인 필요</h1>
              </div>
              <AdminSignOutButton />
            </header>

            <section className={styles.denied}>
              <h2>아직 관리자 목록에 등록되지 않았어요.</h2>
              <p className={styles.copy}>Supabase Auth users 화면에서 아래 UUID를 `admin_users` 테이블에 등록하면 이 계정으로 관리자 화면을 볼 수 있습니다.</p>
              <pre className={styles.codeBox}>{user.id}</pre>
            </section>
          </div>
        </section>
      </main>
    );
  }

  return <AdminHome userEmail={adminRecord.email ?? user.email ?? null} role={adminRecord.role} />;
}
