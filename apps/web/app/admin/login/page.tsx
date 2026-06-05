import Link from "next/link";
import { Home, ShieldCheck } from "lucide-react";
import { getSafeAdminRedirectPath } from "@/lib/admin-auth";
import styles from "../admin.module.css";
import { AdminLoginClient } from "./AdminLoginClient";

type AdminLoginPageProps = {
  searchParams?: {
    next?: string | string[];
    error?: string | string[];
  };
};

function firstSearchValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function authErrorMessage(error: string | undefined): string | null {
  if (!error) {
    return null;
  }

  if (error === "missing_env") {
    return "Supabase 로그인 환경변수가 아직 설정되지 않았어요.";
  }

  if (error === "missing_code") {
    return "로그인 응답을 확인할 수 없어요. 다시 시도해 주세요.";
  }

  if (error === "auth_failed") {
    return "Google 로그인 연결이 완료되지 않았어요. 다시 시도해 주세요.";
  }

  return "관리자 로그인을 다시 시도해 주세요.";
}

export default function AdminLoginPage({ searchParams }: AdminLoginPageProps) {
  const nextPath = getSafeAdminRedirectPath(firstSearchValue(searchParams?.next));
  const errorMessage = authErrorMessage(firstSearchValue(searchParams?.error));

  return (
    <main className={styles.page}>
      <section className={styles.phone} aria-label="관리자 로그인">
        <div className={styles.body}>
          <header className={styles.header}>
            <div>
              <p className={styles.eyebrow}>ADMIN</p>
              <h1>관리자 로그인</h1>
            </div>
            <Link className={styles.ghostLink} href="/" aria-label="홈으로 이동">
              <Home size={18} aria-hidden="true" />
            </Link>
          </header>

          <section className={styles.hero}>
            <span className={styles.heroIcon} aria-hidden="true">
              <ShieldCheck size={28} />
            </span>
            <h2>Google 계정으로 관리자 권한을 확인해요.</h2>
            <p>로그인 후 Supabase Auth UUID가 관리자 목록에 등록되어 있으면 운영 화면으로 이동합니다.</p>
          </section>

          {errorMessage ? <p className={styles.errorText}>{errorMessage}</p> : null}

          <AdminLoginClient nextPath={nextPath} />

          <section className={styles.notice}>
            <h2>처음 로그인하는 팀원이라면</h2>
            <p className={styles.copy}>먼저 Google 로그인으로 계정을 만든 뒤, Supabase Auth users 화면에서 UUID를 확인해 `admin_users` 테이블에 등록해 주세요.</p>
          </section>
        </div>
      </section>
    </main>
  );
}
