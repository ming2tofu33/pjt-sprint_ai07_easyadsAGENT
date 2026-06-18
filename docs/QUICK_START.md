# 🚀 Quick Start Guide

### 1. Prerequisites

| Tool                    | Version / Note                   |
| ----------------------- | -------------------------------- |
| Python                  | 3.12 권장                          |
| Node.js                 | 20+ 권장                           |
| npm 또는 pnpm             | 레포지토리 기준 패키지 매니저 사용              |
| uv                      | Python dependency 관리             |
| Docker / Docker Compose | local infra 실행 시 사용              |
| Supabase CLI            | Supabase local 또는 migration 사용 시 |
| OpenAI API Key          | actual model 실행 시 필요             |

---

### 2. Clone Repository

```bash
git clone https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT.git
cd pjt-sprint_ai07_easyadsAGENT
```

---

### 3. Python Environment

```bash
uv venv
uv sync --group dev
```

---

### 4. Web / BFF Dependencies

```bash
cd apps/bff
npm install

cd ../web
npm install

cd ../..
```

---

### 5. Environment Variables

기본 개발은 mock provider와 local memory backend를 사용할 수 있습니다.

```bash
cp .env.example .env
```

주요 환경 변수는 다음 범주로 구성됩니다.

* OpenAI API key
* Supabase project URL / keys
* Cloudflare R2 storage keys
* Internal API secret
* Provider mode 설정
* DB backend 설정
* Asset storage backend 설정

> 정확한 최신 변수명은 `.env.example`을 Source of Truth로 참고합니다.

---

### 6. Run Development Servers

#### Terminal 1: Orchestrator

```bash
uv run uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8010 --reload
```

#### Terminal 2: BFF

```bash
cd apps/bff
ORCHESTRATOR_BASE_URL=http://127.0.0.1:8010 PORT=4000 npm run dev
```

#### Terminal 3: Web

```bash
cd apps/web
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000 npm run dev
```

---

### 7. Local URLs

| Service      | URL                            |
| ------------ | ------------------------------ |
| Web          | `http://127.0.0.1:3000`        |
| BFF          | `http://127.0.0.1:4000`        |
| Orchestrator | `http://127.0.0.1:8010`        |
| Health Check | `http://127.0.0.1:8010/health` |
| Swagger UI   | `http://127.0.0.1:8010/docs`   |

---

### 8. Local Infra

```bash
docker-compose up -d supabase-db
```

또는 Supabase CLI를 활용해 로컬 환경을 구성하는 경우 (예시 명령어):

```bash
supabase start
supabase db push  # 마이그레이션 정책에 따라 명령어가 다를 수 있습니다
```

⚠️ **주의**: 데이터베이스 마이그레이션 및 적용 방식은 팀의 최신 DB 동기화 정책에 따라 최종 확정된 명령어를 사용하세요.
