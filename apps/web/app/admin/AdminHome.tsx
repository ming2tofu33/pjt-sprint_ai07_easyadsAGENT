import { Database, Images, Settings, UploadCloud } from "lucide-react";
import type { AdminRole } from "@/lib/admin-auth";
import styles from "./admin.module.css";
import { AdminSignOutButton } from "./AdminSignOutButton";

type AdminHomeProps = {
  userEmail: string | null;
  role: AdminRole;
};

export function AdminHome({ userEmail, role }: AdminHomeProps) {
  return (
    <main className={styles.page}>
      <section className={styles.phone} aria-label="관리자 홈">
        <div className={styles.body}>
          <header className={styles.header}>
            <div>
              <p className={styles.eyebrow}>ADMIN</p>
              <h1>관리자 홈</h1>
            </div>
            <AdminSignOutButton />
          </header>

          <section className={styles.hero}>
            <span className={styles.heroIcon} aria-hidden="true">
              <Database size={28} />
            </span>
            <h2>운영 작업을 시작할 준비가 됐어요.</h2>
            <p>
              {userEmail ?? "관리자"} 계정이 {role} 권한으로 확인됐습니다. 다음 단계에서 레퍼런스 관리 도구를 이 화면에 연결할 수 있어요.
            </p>
          </section>

          <section className={styles.cardGrid} aria-label="관리자 기능">
            <button className={styles.adminCard} type="button" data-disabled="true" disabled>
              <span aria-hidden="true">
                <Images size={22} />
              </span>
              <strong>
                레퍼런스 관리
                <small>이미지 목록, 메타데이터, 카테고리 태그를 관리할 예정이에요.</small>
              </strong>
            </button>
            <button className={styles.adminCard} type="button" data-disabled="true" disabled>
              <span aria-hidden="true">
                <UploadCloud size={22} />
              </span>
              <strong>
                업로드 대기함
                <small>R2 업로드와 카탈로그 반영 작업을 연결할 예정이에요.</small>
              </strong>
            </button>
            <button className={styles.adminCard} type="button" data-disabled="true" disabled>
              <span aria-hidden="true">
                <Settings size={22} />
              </span>
              <strong>
                운영 설정
                <small>관리자 권한과 서비스 운영 값을 관리할 예정이에요.</small>
              </strong>
            </button>
          </section>
        </div>
      </section>
    </main>
  );
}
