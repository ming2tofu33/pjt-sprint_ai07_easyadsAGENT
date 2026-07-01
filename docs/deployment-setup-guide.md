# EasyAds Deployment Setup Guide

이 문서는 EasyAds를 `Vercel + Railway + Supabase + Cloudflare R2 + Modal` 조합으로 배포하기 위한 팀 공용 가이드입니다.

목표는 다음과 같습니다.

- Vercel에서 Next.js UI를 배포한다.
- Railway에서 BFF와 orchestrator API를 배포한다.
- Supabase에서 Auth, Postgres DB, RLS 기반 권한을 관리한다.
- Cloudflare R2에 원본 사진, 결과 이미지, 썸네일을 저장한다.
- Modal에서 SD 3.5 Large, FLUX, Gemma 같은 무거운 모델 실행을 담당한다.

> 현재 코드 상태 기준으로 `apps/web` UI와 BFF/orchestrator mock API 흐름은 배포 가능하다. R2, Supabase, Modal 연동은 운영형 사진 생성 플로우를 위해 추가 구현이 필요한 단계로 분리해서 진행한다.

## 1. 전체 아키텍처

```text
Browser
  -> Vercel
     - apps/web Next.js UI

  -> Railway BFF
     - apps/bff Fastify API
     - CORS, request validation, orchestrator proxy

  -> Railway Orchestrator
     - orchestrator FastAPI
     - marketing chat, photo flow, reference, generation jobs
     - OpenAI SDK / Responses API based workflow planning
     - structured output, tool calling, response state tracking

  -> Supabase
     - Auth
     - Postgres
     - Row Level Security
     - job, thread, asset, workflow metadata

  -> Cloudflare R2
     - source uploads
     - generated outputs
     - thumbnails
     - intermediate artifacts

  -> Modal
     - GPU workers
     - SD 3.5 Large / FLUX / Gemma execution
     - model cache or Modal Volume
```

역할을 한 줄로 정리하면 다음과 같습니다.

```text
화면: Vercel
API: Railway
DB/Auth: Supabase
파일: Cloudflare R2
AI workflow 규격: OpenAI SDK, Railway orchestrator 내부에서 사용
GPU 모델 실행: Modal
```

## 2. 배포 단계 요약

처음부터 모든 것을 한 번에 붙이지 말고 다음 순서로 진행합니다.

```text
Phase 0. 로컬 빌드 검증
Phase 1. Vercel UI 배포
Phase 2. Railway BFF 배포
Phase 3. Railway orchestrator 배포
Phase 4. Vercel UI와 Railway BFF 연결
Phase 5. Supabase 프로젝트와 DB 스키마 준비
Phase 6. Cloudflare R2 버킷과 키 준비
Phase 7. Modal GPU worker 준비
Phase 8. OpenAI SDK workflow, Supabase, R2, Modal 연동
Phase 9. 전체 플로우 smoke test
```

현재 MVP 확인만 먼저 하려면 `Phase 0`부터 `Phase 4`까지 먼저 완료합니다.

실제 사진 업로드, 저장, GPU 생성까지 보려면 `Phase 5`부터 `Phase 9`까지 진행합니다.

## 3. 사전 준비

### 3.1 계정

필요한 계정은 다음과 같습니다.

- Vercel
- Railway
- Supabase
- Cloudflare
- Modal
- Hugging Face, SD/FLUX/Gemma 모델을 다운로드할 경우
- OpenAI, OpenAI API 기반 이미지/LLM 경로를 사용할 경우

### 3.2 로컬 필수 도구

```bash
node --version
npm --version
python3 --version
git --version
```

권장 버전:

- Node.js: 20 계열
- Python: `.python-version` 기준
- npm: lockfile를 사용할 수 있는 최신 npm

### 3.3 배포 전 로컬 검증

루트에서 orchestrator 테스트:

```bash
python3 -m pytest orchestrator/tests
```

웹 앱 검증:

```bash
cd apps/web
npm install
npm run lint
npm run test
npm run build
```

BFF 검증:

```bash
cd apps/bff
npm install
npm run test
```

현재 확인된 웹 빌드 기준:

```bash
cd apps/web
npm run build
```

이 명령은 Vercel 배포 전에 반드시 통과해야 합니다.

## 4. 환경변수 그룹

환경변수는 서비스별로 분리해서 관리합니다. `.env` 파일은 절대 커밋하지 않습니다.

### 4.1 Vercel, web

Vercel 프로젝트의 `apps/web`에 설정합니다.

```text
NEXT_PUBLIC_BFF_BASE_URL=https://<railway-bff-domain>
```

주의:

- `NEXT_PUBLIC_BFF_BASE_URL`은 브라우저에 노출되는 값입니다.
- 여기에 secret key를 넣으면 안 됩니다.
- 값이 비어 있으면 현재 프론트 코드는 `http://127.0.0.1:4000`을 기본값으로 사용합니다. 배포 환경에서는 반드시 Railway BFF URL로 설정해야 합니다.

### 4.2 Railway, BFF

Railway의 `apps/bff` 서비스에 설정합니다.

```text
NODE_ENV=production
PORT=<Railway가 자동 제공>
HOST=0.0.0.0
ORCHESTRATOR_BASE_URL=https://<railway-orchestrator-domain>
CORS_ORIGIN=https://<vercel-domain>
```

현재 BFF의 사진 업로드 경로는 로컬 디스크(`data/uploads`) 기반입니다.
R2 업로드와 레퍼런스 이미지 URL 생성은 orchestrator가 담당하므로 BFF에는 R2 secret을 넣지 않습니다.

Supabase 연동 후 추가될 값:

```text
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=
```

주의:

- `SUPABASE_SERVICE_ROLE_KEY`는 Railway 서버에만 둡니다.
- Vercel 브라우저 환경에는 절대 넣지 않습니다.

### 4.3 Railway, orchestrator

Railway의 orchestrator 서비스에 설정합니다.

```text
EASYADS_ENV=production
PYTHONUNBUFFERED=1
PYTHONPATH=/app

T2I_DEFAULT_ENGINE=mock
T2I_OUTPUT_DIR=data/outputs
T2I_ALLOW_API_CALLS=false
T2I_ENABLE_API_COST_GUARD=true
T2I_GPT_IMAGE_MODEL=gpt-image-2
T2I_SD35_MODEL_ID=stabilityai/stable-diffusion-3.5-large
T2I_FLUX_MODEL_ID=black-forest-labs/FLUX.1-schnell
EASYADS_T2I_FLUX2_KLEIN_MODEL_ID=black-forest-labs/FLUX.2-klein-4B
EASYADS_T2I_FLUX2_KLEIN_BACKEND=modal
EASYADS_T2I_FLUX2_KLEIN_STEPS=4
EASYADS_T2I_FLUX2_KLEIN_GUIDANCE_SCALE=1.0

EASYADS_ENABLE_EXTERNAL_T2I=false
EASYADS_ENABLE_GPT_IMAGE_2=false
EASYADS_ENABLE_SD35_LOCAL=false
EASYADS_ENABLE_FLUX2_KLEIN_LOCAL=false

LLM_ENABLE_API_CALL=false
LLM_DEFAULT_PROVIDER=mock
LLM_PROVIDER_STRICT_MODE=true
LLM_REQUEST_TIMEOUT_SECONDS=30

VISION_UPLOAD_DIR=data/uploads
VISION_PROCESSED_DIR=data/processed
VISION_MAX_FILE_SIZE_MB=20
VISION_MAX_IMAGE_PIXELS=12000000
VISION_DEFAULT_MAX_SIDE=1536
VISION_SAVE_PREVIEW=true
VISION_PREVIEW_MAX_SIDE=512
```

OpenAI SDK 규격으로 워크플로우를 통일할 때 추가:

```text
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_DEFAULT_MODEL=
OPENAI_SMALL_MODEL=
OPENAI_REASONING_MODEL=
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_REQUEST_TIMEOUT_SECONDS=30
OPENAI_MAX_OUTPUT_TOKENS=
OPENAI_STORE_RESPONSES=true
OPENAI_WORKFLOW_STRICT_SCHEMA=true
OPENAI_WORKFLOW_TRACE_ENABLED=true
```

기존 `LLM_*` 환경변수는 OpenAI SDK adapter가 완전히 들어가기 전까지의 호환 설정으로 둡니다.
최종적으로는 orchestrator의 LLM/brief/planning 호출을 OpenAI SDK의 Responses API 기반 adapter로 통일합니다.

Modal 연동을 켤 때 추가:

```text
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
EASYADS_T2I_EXECUTION_BACKEND=modal
EASYADS_ENABLE_MODAL_EXECUTION=true
EASYADS_MODAL_POLL_ON_GET=true
EASYADS_MODAL_APP_NAME=easyads-t2i
EASYADS_MODAL_FUNCTION_NAME=generate_image
EASYADS_MODAL_ENVIRONMENT=main
EASYADS_MODAL_RESULT_TRANSPORT=inline_base64
EASYADS_MODAL_POLL_TIMEOUT_SECONDS=0
```

초기 배포에서는 `T2I_DEFAULT_ENGINE=mock`, `LLM_DEFAULT_PROVIDER=mock`으로 둡니다.
실제 비용이 발생하는 경로는 smoke test가 끝난 뒤 명시적으로 켭니다.

OpenAI SDK 사용 원칙:

```text
Railway orchestrator만 OpenAI SDK를 호출한다.
Vercel browser와 Modal worker에는 OPENAI_API_KEY를 넣지 않는다.
대화 상태는 Supabase thread state와 OpenAI response id를 함께 저장한다.
브리프/문구/생성 계획은 structured output schema로 검증한다.
tool/function call은 Railway backend가 실제 실행한다.
```

### 4.4 Supabase

Supabase dashboard에서 확인해야 하는 값:

```text
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=
```

사용 위치:

```text
SUPABASE_ANON_KEY
  -> 필요할 경우 Vercel client 또는 server component에서 사용

SUPABASE_SERVICE_ROLE_KEY
  -> Railway backend 전용

DATABASE_URL
  -> Railway backend migration 또는 server-side query 전용
```

Railway처럼 장시간 떠 있는 서버는 Supabase connection pooler 또는 애플리케이션 pool을 사용합니다.
서버리스/짧은 연결이 많은 환경에서는 transaction pooler를 우선 고려합니다.

### 4.5 Cloudflare R2

Cloudflare dashboard에서 준비할 값은 orchestrator 서비스에 등록합니다.

```text
EASYADS_R2_ACCESS_KEY_ID=...
EASYADS_R2_SECRET_ACCESS_KEY=...
EASYADS_R2_BUCKET=easyads-assets-prod
EASYADS_R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
EASYADS_R2_REGION=auto
EASYADS_R2_URL_MODE=signed
EASYADS_R2_SIGNED_URL_TTL_SECONDS=3600
```

초기 프로덕션은 `signed` 모드를 권장합니다. 이 모드는 bucket을 공개하지 않고 orchestrator가 만료 시간이 있는 presigned URL을 생성해 UI에 전달합니다. public bucket 또는 custom domain을 쓸 때만 `EASYADS_R2_URL_MODE=public`과 `EASYADS_R2_PUBLIC_BASE_URL=https://...`를 추가합니다.

서비스 레퍼런스 갤러리처럼 공개해도 되는 이미지가 public R2 bucket에 올라가 있다면 아래 값을 orchestrator에 추가합니다.

```text
EASYADS_R2_URL_MODE=public
EASYADS_R2_PUBLIC_BASE_URL=https://<public-r2-or-cdn-base-url>
```

배포 사이트에서 레퍼런스 이미지가 보이는지 확인할 때는 BFF 응답에서 `thumbnail_url`이 `null`이 아닌지 먼저 확인합니다.

```bash
curl -s https://<railway-bff-domain>/api/references?limit=1 | jq '.items[0].thumbnail_url'
```

정상 예시:

```text
"https://<public-r2-or-cdn-base-url>/reference-templates/v1/ref_cafe_1_0_007/source.png"
```

추천 버킷:

```text
easyads-assets-dev
easyads-assets-prod
```

추천 object key 규칙:

```text
workspaces/<workspace_id>/threads/<thread_id>/uploads/<asset_id>.<ext>
workspaces/<workspace_id>/threads/<thread_id>/outputs/<output_id>.<ext>
workspaces/<workspace_id>/threads/<thread_id>/thumbnails/<output_id>.webp
workspaces/<workspace_id>/threads/<thread_id>/artifacts/<job_id>/<name>.json
```

### 4.6 Modal

초기 연결 smoke에서는 Modal secret이 필요하지 않습니다. `modal_apps/easyads_t2i_worker.py`는 GPU와 모델 없이 mock 이미지를 반환해서 `Railway -> Modal -> R2` 경로만 검증합니다.

실제 SD/FLUX 모델을 붙일 때 Modal secrets에 넣을 값:

```text
HF_TOKEN=
```

Railway에서 Modal을 호출하려면 Railway에 다음 값이 필요합니다.

```text
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
EASYADS_T2I_EXECUTION_BACKEND=modal
EASYADS_ENABLE_MODAL_EXECUTION=true
EASYADS_MODAL_POLL_ON_GET=true
EASYADS_MODAL_APP_NAME=easyads-t2i
EASYADS_MODAL_FUNCTION_NAME=generate_image
EASYADS_MODAL_ENVIRONMENT=main
EASYADS_MODAL_RESULT_TRANSPORT=inline_base64
EASYADS_MODAL_POLL_TIMEOUT_SECONDS=0
```

`EASYADS_MODAL_FUNCTION_NAME=generate_image`는 GPU 없는 mock/R2 smoke용입니다.
실제 FLUX.2 Klein 4B를 실행할 때는 모델별 함수 변수를 추가합니다.

```text
EASYADS_MODAL_FLUX2_KLEIN_FUNCTION_NAME=generate_flux2_klein_image
```

모델 weight는 R2가 아니라 Modal cache 또는 Modal Volume에 둡니다.
R2는 사용자 파일과 결과물 저장소로만 사용합니다.

## 5. Phase 0, 로컬 검증

### 5.1 web

```bash
cd apps/web
npm install
npm run lint
npm run test
npm run build
```

### 5.2 BFF

```bash
cd apps/bff
npm install
npm run test
PORT=4000 ORCHESTRATOR_BASE_URL=http://127.0.0.1:8010 npm run dev
```

헬스체크:

```bash
curl http://127.0.0.1:4000/health
```

기대 응답:

```json
{"status":"ok"}
```

### 5.3 orchestrator

```bash
uv run uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8010
```

또는 `uv`를 쓰지 않는 환경:

```bash
python3 -m uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8010
```

헬스체크:

```bash
curl http://127.0.0.1:8010/health
```

기대 응답:

```json
{"status":"ok"}
```

### 5.4 세 프로세스 연결 확인

터미널 1:

```bash
uv run uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8010
```

터미널 2:

```bash
cd apps/bff
ORCHESTRATOR_BASE_URL=http://127.0.0.1:8010 PORT=4000 npm run dev
```

터미널 3:

```bash
cd apps/web
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000 npm run dev
```

브라우저:

```text
http://127.0.0.1:3000
```

## 6. Phase 1, Vercel UI 배포

### 6.1 프로젝트 생성

Vercel에서 GitHub repo를 import합니다.

설정:

```text
Framework Preset: Next.js
Root Directory: apps/web
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

### 6.2 환경변수

초기에는 BFF 배포 전이므로 비워두거나 임시 preview BFF URL을 넣을 수 있습니다.
최종적으로는 다음 값이 필요합니다.

```text
NEXT_PUBLIC_BFF_BASE_URL=https://<railway-bff-domain>
```

### 6.3 배포 확인

Vercel 배포 후 다음 화면을 확인합니다.

```text
/
/onboarding
/studio
/generate/chat
/generate/photo
/reference
/ads
/brand
/my
```

주의:

- BFF 연결 전에는 API가 필요한 일부 동작이 실패하거나 fallback/mock 흐름으로 보일 수 있습니다.
- UI만 먼저 확인하는 것은 정상입니다.

## 7. Phase 2, Railway BFF 배포

### 7.1 서비스 생성

Railway에서 repo를 연결하고 BFF 서비스를 하나 만듭니다.

설정:

```text
Service name: easyads-bff
Root Directory: apps/bff
Install Command: npm install
Start Command: npm start
```

Railway가 `PORT`를 자동으로 주입합니다.
코드는 `process.env.PORT || 4000`을 사용하므로 Railway 환경과 잘 맞습니다.

### 7.2 환경변수

```text
NODE_ENV=production
HOST=0.0.0.0
ORCHESTRATOR_BASE_URL=https://<railway-orchestrator-domain>
CORS_ORIGIN=https://<vercel-domain>
```

orchestrator 배포 전에는 `ORCHESTRATOR_BASE_URL`을 임시 값으로 둘 수 있습니다.
다만 API proxy 요청은 실패합니다.

### 7.3 헬스체크

배포 URL이 나오면 확인합니다.

```bash
curl https://<railway-bff-domain>/health
```

기대 응답:

```json
{"status":"ok"}
```

## 8. Phase 3, Railway orchestrator 배포

### 8.1 서비스 생성

Railway에서 repo를 연결하고 orchestrator 서비스를 하나 더 만듭니다.

설정:

```text
Service name: easyads-orchestrator
Root Directory: .
Dockerfile Path: Dockerfile.orchestrator
Start Command: 비워둠
```

루트의 기본 `Dockerfile`은 CUDA/GPU 개발 컨테이너용이며, 마지막 명령이 API 서버 실행이 아니라 컨테이너 유지용입니다.
Railway orchestrator 서비스는 반드시 `Dockerfile.orchestrator`를 사용합니다.

Railway UI에서 Dockerfile Path 필드가 보이지 않으면 orchestrator 서비스 Variables에 다음을 추가합니다.

```text
RAILWAY_DOCKERFILE_PATH=Dockerfile.orchestrator
```

`Dockerfile.orchestrator`는 `requirements.txt`를 설치하고 다음 명령으로 FastAPI 서버를 실행합니다.

```bash
uvicorn orchestrator.app.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

### 8.2 환경변수

초기 mock 배포:

```text
EASYADS_ENV=production
PYTHONUNBUFFERED=1
PYTHONPATH=/app
T2I_DEFAULT_ENGINE=mock
T2I_ALLOW_API_CALLS=false
T2I_ENABLE_API_COST_GUARD=true
LLM_ENABLE_API_CALL=false
LLM_DEFAULT_PROVIDER=mock
LLM_PROVIDER_STRICT_MODE=true
```

실제 API 또는 Modal 연동은 나중에 켭니다.

```text
OPENAI_API_KEY=
HF_TOKEN=
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
```

### 8.3 헬스체크

```bash
curl https://<railway-orchestrator-domain>/health
```

기대 응답:

```json
{"status":"ok"}
```

### 8.4 BFF와 연결

BFF 서비스의 환경변수를 업데이트합니다.

```text
ORCHESTRATOR_BASE_URL=https://<railway-orchestrator-domain>
```

BFF를 redeploy한 뒤 다음을 확인합니다.

```bash
curl https://<railway-bff-domain>/health
curl https://<railway-orchestrator-domain>/health
```

## 9. Phase 4, Vercel과 Railway 연결

Vercel web 프로젝트에 환경변수를 설정합니다.

```text
NEXT_PUBLIC_BFF_BASE_URL=https://<railway-bff-domain>
```

Vercel을 redeploy합니다.

확인할 플로우:

```text
1. Vercel URL 접속
2. /generate/chat 이동
3. 프롬프트 입력
4. BFF -> orchestrator 호출 여부 확인
5. Railway BFF logs 확인
6. Railway orchestrator logs 확인
```

브라우저 개발자 도구 Network에서 API 요청이 다음 도메인으로 나가야 합니다.

```text
https://<railway-bff-domain>/api/...
```

`http://127.0.0.1:4000`으로 나가면 Vercel 환경변수가 잘못된 것입니다.

## 10. Phase 5, Supabase 설정

### 10.1 프로젝트 생성

Supabase에서 새 project를 만듭니다.

추천:

```text
Project name: easyads-prod
Region: 주요 사용자가 가까운 지역
Database password: password manager에 저장
```

개발과 운영을 분리하려면 다음처럼 만듭니다.

```text
easyads-dev
easyads-prod
```

### 10.2 Auth

MVP에서 사용할 로그인 방식을 정합니다.

추천 초기 옵션:

```text
Email magic link 또는 Email/password
```

Vercel URL이 정해진 뒤 Supabase Auth redirect URL에 추가합니다.

```text
https://<vercel-domain>
https://<vercel-domain>/auth/callback
http://127.0.0.1:3000
http://127.0.0.1:3000/auth/callback
```

### 10.3 DB 스키마 방향

우리 제품은 "대화창 하나에서 결과물 하나를 만든다"는 구조입니다.
따라서 DB 중심은 `chat_threads`입니다.

추천 테이블:

```text
profiles
workspaces
workspace_members
brand_kits
projects
chat_threads
chat_messages
chat_message_assets
assets
workflow_runs
generation_jobs
generation_outputs
generation_job_events
usage_events
feedback_events
```

핵심 관계:

```text
workspaces
  -> chat_threads
     -> chat_messages
     -> workflow_runs
     -> generation_jobs
     -> generation_outputs
  -> assets
  -> usage_events
```

OpenAI SDK/Responses API를 기준으로 워크플로우를 통일하므로, `workflow_runs`를 추가합니다.
이 테이블은 브리프 생성, 문구 후보 생성, 이미지 생성 계획, validation 같은 OpenAI SDK 호출 기록을 남깁니다.
Modal GPU 실행 자체는 `generation_jobs`에 기록하지만, 그 앞단의 "무엇을 어떻게 만들지 결정한 AI workflow"는 `workflow_runs`에 남깁니다.

권장 `workflow_runs` 필드:

```text
id
workspace_id
thread_id
job_id nullable
created_by
provider: openai
request_type: copy_candidates | creative_brief | generation_plan | validation | other
status: queued | running | succeeded | failed
model
response_id nullable
previous_response_id nullable
input_json jsonb
output_json jsonb
tool_calls jsonb
usage_json jsonb
error_code nullable
error_message nullable
started_at
finished_at
created_at
```

`chat_threads`에는 현재 대화 상태를 이어가기 위한 OpenAI response id를 저장합니다.

```text
chat_threads.openai_last_response_id nullable
chat_threads.workflow_state jsonb nullable
```

`chat_messages`와 `generation_jobs`에도 추적 컬럼을 둡니다.

```text
chat_messages.openai_response_id nullable
generation_jobs.workflow_run_id nullable
generation_jobs.openai_response_id nullable
generation_jobs.openai_previous_response_id nullable
generation_jobs.workflow_provider: openai
generation_jobs.workflow_model nullable
generation_jobs.workflow_input jsonb nullable
generation_jobs.workflow_output jsonb nullable
```

### 10.4 RLS 원칙

Supabase public schema의 사용자 데이터 테이블은 RLS를 켭니다.

```sql
alter table public.chat_threads enable row level security;
alter table public.chat_messages enable row level security;
alter table public.assets enable row level security;
alter table public.workflow_runs enable row level security;
alter table public.generation_jobs enable row level security;
alter table public.generation_outputs enable row level security;
```

권한 기준:

```text
사용자는 자신이 속한 workspace 데이터만 접근 가능
Railway backend는 service role로 내부 작업 수행 가능
```

중요:

- RLS는 나중에 붙이는 것보다 처음부터 켜는 것이 안전합니다.
- 정책에 쓰이는 `workspace_id`, `user_id` 계열 컬럼에는 인덱스가 필요합니다.

### 10.5 필수 인덱스 방향

```sql
create index chat_threads_workspace_recent_idx
on chat_threads (workspace_id, last_message_at desc)
where archived_at is null;

create index chat_messages_thread_sequence_idx
on chat_messages (thread_id, sequence_no);

create index workflow_runs_thread_created_idx
on workflow_runs (thread_id, created_at desc);

create index workflow_runs_response_id_idx
on workflow_runs (response_id)
where response_id is not null;

create index generation_jobs_thread_created_idx
on generation_jobs (thread_id, created_at desc);

create index generation_jobs_active_idx
on generation_jobs (created_at)
where status in ('queued', 'running');

create index assets_workspace_created_idx
on assets (workspace_id, created_at desc);

create unique index assets_bucket_object_key_idx
on assets (bucket, object_key);

create unique index generation_outputs_one_final_per_thread_idx
on generation_outputs (thread_id)
where is_final = true;
```

### 10.6 Railway 연결

현재 코드 기준으로 Supabase DB persistence를 켜는 서비스는 Railway `orchestrator`입니다.
`apps/bff`는 orchestrator proxy 역할이므로 지금 단계에서는 DB에 직접 연결하지 않습니다.

Supabase Dashboard에서 먼저 `supabase/migrations/20260602_core_schema_v1.sql` 내용을 적용합니다.
그 다음 Railway orchestrator 서비스에 다음 값을 넣습니다.

```text
EASYADS_DB_BACKEND=postgres
DATABASE_URL=
EASYADS_DEMO_WORKSPACE_ID=
EASYADS_DEMO_USER_ID=demo
```

`DATABASE_URL`은 Supabase Dashboard의 `Connect` 패널에서 Postgres connection string을 복사합니다.
현재 repository는 요청 시점에 짧게 DB connection을 열고 닫기 때문에, 운영 배포에서는 Supabase pooler connection string을 우선 사용합니다.

Auth/API 연동 단계에서 추가로 필요해지는 값:

```text
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

주의:

- 브라우저에는 `SUPABASE_SERVICE_ROLE_KEY`를 절대 노출하지 않습니다.
- 현재 Postgres repository path는 `DATABASE_URL`만 사용합니다.
- `EASYADS_DB_BACKEND=postgres`를 켠 뒤에는 `/api/generation-jobs` 계열 API가 Supabase에 job/thread/output 메타데이터를 저장합니다.
- DB 연결은 Supabase connection pooler 사용을 우선 고려합니다.

## 11. Phase 6, Cloudflare R2 설정

### 11.1 버킷 생성

Cloudflare R2에서 버킷을 만듭니다.

추천:

```text
easyads-assets-dev
easyads-assets-prod
```

### 11.2 API token 생성

R2 object read/write가 가능한 access key를 만듭니다.

필요 값:

```text
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
R2_ENDPOINT
```

### 11.3 공개 접근 전략

이미지를 사용자에게 보여주는 방식은 둘 중 하나를 고릅니다.

Option A, signed URL:

```text
private bucket
Railway가 짧은 만료시간 signed URL 발급
보안 좋음
구현 조금 더 필요
```

Option B, public read domain:

```text
결과 이미지 일부 public read
UI 구현 쉬움
비공개 사용자 파일에는 부적합
```

추천:

```text
업로드 원본: private + signed URL
생성 결과: private + signed URL 우선
공유 링크 기능이 생기면 public/share token 별도 설계
```

### 11.4 DB에는 파일 메타데이터만 저장

`assets` 테이블에는 다음만 저장합니다.

```text
bucket
object_key
mime_type
size_bytes
width
height
checksum_sha256
metadata
```

이미지 binary와 base64는 Supabase DB에 저장하지 않습니다.

## 12. Phase 7, Modal 설정

### 12.1 Modal workspace 준비

Modal 계정을 만들고 CLI를 설정합니다.

```bash
uv run modal token new
```

또는 이미 Modal dashboard에서 token을 만들었다면:

```bash
uv run modal token set --token-id <MODAL_TOKEN_ID> --token-secret <MODAL_TOKEN_SECRET>
```

Railway orchestrator에는 `.modal.toml`이 없으므로 `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` 환경변수를 직접 넣습니다.

### 12.2 mock worker 배포

먼저 GPU/모델 없는 mock Modal worker로 연결을 검증합니다.

```bash
uv run modal deploy modal_apps/easyads_t2i_worker.py
```

배포 이름:

```text
EASYADS_MODAL_APP_NAME=easyads-t2i
EASYADS_MODAL_FUNCTION_NAME=generate_image
```

같은 파일에는 실제 FLUX.2 Klein 4B worker와 SD3.5 Large worker도 함께 들어 있습니다. 이 함수들은 GPU와 Hugging Face secret을 사용합니다.

```text
EASYADS_MODAL_FLUX2_KLEIN_FUNCTION_NAME=generate_flux2_klein_image
EASYADS_MODAL_SD35_FUNCTION_NAME=generate_sd35_large_image
```

### 12.3 Railway Modal 변수

Railway orchestrator에 넣습니다.

```text
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
EASYADS_T2I_EXECUTION_BACKEND=modal
EASYADS_ENABLE_MODAL_EXECUTION=true
EASYADS_MODAL_POLL_ON_GET=true
EASYADS_MODAL_APP_NAME=easyads-t2i
EASYADS_MODAL_FUNCTION_NAME=generate_image
EASYADS_MODAL_FLUX2_KLEIN_FUNCTION_NAME=generate_flux2_klein_image
EASYADS_MODAL_SD35_FUNCTION_NAME=generate_sd35_large_image
EASYADS_MODAL_ENVIRONMENT=main
EASYADS_MODAL_RESULT_TRANSPORT=inline_base64
EASYADS_MODAL_POLL_TIMEOUT_SECONDS=0
```

적용 후 orchestrator를 redeploy합니다.

orchestrator는 `runMode`에 따라 Modal 함수를 자동 선택합니다.

```text
mock/smoke        -> EASYADS_MODAL_FUNCTION_NAME
flux2_klein_4b    -> EASYADS_MODAL_FLUX2_KLEIN_FUNCTION_NAME
sd35_large_real   -> EASYADS_MODAL_SD35_FUNCTION_NAME
```

실제 FLUX.2 Klein 4B smoke 요청:

```json
{
  "userInput": "Create a premium cafe ad",
  "runMode": "flux2_klein_4b",
  "metadata": {
    "width": 768,
    "height": 768,
    "t2i_params": {
      "num_inference_steps": 4,
      "guidance_scale": 1.0
    }
  }
}
```

실제 SD3.5 Large smoke 요청:

```json
{
  "userInput": "Create a premium cafe ad",
  "runMode": "sd35_large_real",
  "metadata": {
    "width": 768,
    "height": 768,
    "t2i_params": {
      "num_inference_steps": 8,
      "guidance_scale": 4.0
    }
  }
}
```

### 12.4 실제 모델 secrets 준비

실제 SD/FLUX worker로 바꿀 때 Modal secret에는 모델 다운로드에 필요한 값을 넣습니다.

```text
HF_TOKEN
```

권장 secret 이름:

```text
easyads-hf-token
```

생성:

```bash
uv run modal secret create easyads-hf-token HF_TOKEN="$HF_TOKEN"
```

현재 R2 업로드는 Railway orchestrator가 담당하므로 mock worker 단계에서는 Modal에 R2 secret을 넣지 않습니다.

### 12.5 모델 저장 위치

모델 weight:

```text
Hugging Face Hub -> Modal cache 또는 Modal Volume
```

사용자 파일과 결과물:

```text
Cloudflare R2
```

모델 weight를 R2에 넣는 것은 추천하지 않습니다.
R2는 서비스 파일과 산출물 저장소로 사용하고, 모델 weight는 Modal 쪽 캐시/볼륨을 사용합니다.

### 12.6 GPU 선택

초기 MVP 추천:

```text
L40S
```

실제 FLUX.2 Klein 4B worker의 기본값은 `EASYADS_MODAL_FLUX_GPU=L40S`입니다.
실제 SD3.5 Large worker의 기본값은 `EASYADS_MODAL_SD35_GPU=L40S`입니다.
Modal worker 배포 전에 로컬 환경변수로 바꾸면 다른 GPU로 배포할 수 있습니다.

```bash
EASYADS_MODAL_FLUX_GPU=H100 EASYADS_MODAL_SD35_GPU=H100 uv run modal deploy modal_apps/easyads_t2i_worker.py
```

SD 3.5 Large와 FLUX는 모델별 VRAM 요구량이 다르므로 실제 worker 전환 전 한 모델씩 smoke합니다.

더 가벼운 테스트:

```text
mock worker의 generate_image 함수
```

고품질/고속 생성:

```text
A100 또는 H100
```

주의:

- GPU 비용은 실제 실행 시간 기준으로 발생합니다.
- warm container 설정은 latency를 줄이지만 비용을 늘립니다.
- MVP에서는 scale-to-zero를 기본으로 둡니다.

### 12.5 Railway와 Modal 연결

Railway backend가 Modal function 또는 web endpoint를 호출합니다.
이때 Modal은 OpenAI SDK workflow를 대체하지 않습니다.
OpenAI SDK는 Railway orchestrator 안에서 브리프, 프롬프트, tool call, 생성 계획을 만드는 표준 인터페이스입니다.
Modal은 그 계획을 받아 실제 GPU 모델을 실행하는 worker입니다.

흐름:

```text
Railway
  -> OpenAI SDK workflow로 generation plan 생성
  -> workflow_runs row 저장
  -> generation_jobs row 생성
  -> R2 input object_key 확인
  -> Modal 호출
  -> Modal run id 저장
  -> Modal이 결과를 R2에 저장
  -> Railway callback 또는 polling으로 job 상태 업데이트
```

## 13. OpenAI SDK workflow contract

OpenAI SDK 규격 통일의 목표는 모델 호출 방식을 하나의 계약으로 맞추는 것입니다.
대화 상태, structured output, tool/function calling, usage 추적을 모두 같은 형태로 저장합니다.

### 13.1 호출 위치

OpenAI SDK 호출은 Railway orchestrator에서만 수행합니다.

```text
Vercel
  -> OpenAI SDK 직접 호출 금지

Railway BFF
  -> 요청 검증, 인증, orchestrator proxy
  -> 가능하면 OpenAI SDK 직접 호출 금지

Railway orchestrator
  -> OpenAI SDK 호출
  -> Responses API 기반 workflow 실행
  -> structured output 검증
  -> tool/function call 실행 결정

Modal
  -> OpenAI SDK workflow 결과를 입력으로 받아 GPU 생성 실행
  -> OPENAI_API_KEY는 기본적으로 넣지 않음
```

### 13.2 표준 workflow envelope

OpenAI SDK 호출 결과는 DB와 로그에서 다음 형태로 추적합니다.

```json
{
  "provider": "openai",
  "requestType": "generation_plan",
  "model": "OPENAI_DEFAULT_MODEL",
  "responseId": "resp_...",
  "previousResponseId": "resp_...",
  "status": "succeeded",
  "input": {},
  "output": {},
  "toolCalls": [],
  "usage": {},
  "error": null
}
```

이 envelope는 `workflow_runs.input_json`, `workflow_runs.output_json`, `workflow_runs.tool_calls`, `workflow_runs.usage_json`에 저장합니다.

### 13.3 대화 상태 관리

OpenAI Responses API의 대화 이어가기 값은 Supabase thread와 함께 저장합니다.

```text
chat_threads.openai_last_response_id
workflow_runs.previous_response_id
workflow_runs.response_id
```

새 사용자 메시지가 들어오면:

```text
1. chat_threads.openai_last_response_id를 읽는다.
2. OpenAI SDK 호출 시 previous_response_id로 넘긴다.
3. 응답의 response id를 workflow_runs.response_id에 저장한다.
4. chat_threads.openai_last_response_id를 최신 값으로 갱신한다.
```

OpenAI에 저장된 conversation state만 믿지 않고, Supabase에도 핵심 메시지와 결과를 저장합니다.
이렇게 해야 재현, 디버깅, vendor 전환이 가능합니다.

### 13.4 structured output 기준

다음 결과는 자유 텍스트가 아니라 schema 기반 structured output으로 받습니다.

```text
copy_candidates
creative_brief
generation_plan
image_prompt
validation_result
usage_summary
```

권장:

```text
Python orchestrator
  -> Pydantic model을 source of truth로 사용

TypeScript web/BFF
  -> 동일 schema를 Zod 또는 generated type으로 맞춤

DB
  -> output_json에 원본 저장
  -> 자주 검색할 값은 별도 컬럼으로 승격
```

### 13.5 tool/function calling 기준

OpenAI model이 직접 외부 시스템을 조작하지 않습니다.
모델은 tool call을 제안하고, 실제 실행은 Railway orchestrator가 수행합니다.

초기 tool 후보:

```text
create_generation_job
select_reference_template
save_brand_kit_snapshot
request_modal_generation
record_usage_event
validate_asset_access
```

tool 실행 결과도 `workflow_runs.tool_calls`와 `generation_job_events`에 기록합니다.

### 13.6 모델 선택 원칙

환경변수로 모델 역할을 나눕니다.

```text
OPENAI_SMALL_MODEL
  -> 빠른 분류, 옵션 질문, 요약

OPENAI_DEFAULT_MODEL
  -> 브리프, 문구 후보, 생성 계획

OPENAI_REASONING_MODEL
  -> 복잡한 검증, 실패 원인 분석, 고난도 planning

OPENAI_IMAGE_MODEL
  -> OpenAI 이미지 생성/편집 경로를 사용할 경우
```

모델 이름은 코드에 하드코딩하지 않고 환경변수로 관리합니다.
테스트 fixture나 과거 결과 재현용 snapshot은 별도로 보존할 수 있습니다.

### 13.7 실패와 재시도

OpenAI SDK 호출 실패 시:

```text
workflow_runs.status = failed
workflow_runs.error_code = ...
workflow_runs.error_message = ...
generation_job_events에 workflow_failed 이벤트 저장
```

재시도 시:

```text
새 workflow_runs row를 생성한다.
기존 workflow_runs row를 덮어쓰지 않는다.
idempotency key를 사용해 중복 비용을 막는다.
```

## 14. Phase 8, 실제 사진 생성 플로우 구현 체크리스트

현재 코드에서 운영형 연동을 위해 필요한 작업입니다.

### 14.1 BFF photo upload를 R2 기반으로 변경

현재:

```text
apps/bff/src/app.js
POST /api/generate/photo/upload
-> local data/uploads에 저장
```

변경:

```text
POST /api/generate/photo/upload
-> R2 upload
-> Supabase assets row insert
-> sourceImagePath 대신 assetId 또는 r2 object key 반환
```

추천 응답:

```json
{
  "assetId": "...",
  "sourceImagePath": "r2://easyads-assets-prod/workspaces/.../uploads/...",
  "fileName": "photo.png",
  "mimeType": "image/png",
  "sizeBytes": 12345
}
```

### 14.2 OpenAI SDK workflow를 Supabase에 저장

생성 요청 시 먼저 OpenAI SDK workflow를 실행합니다.

```text
1. chat_threads.openai_last_response_id 읽기
2. OpenAI SDK Responses API 호출
3. structured output으로 creative brief와 generation plan 받기
4. workflow_runs row 생성
5. chat_threads.openai_last_response_id 갱신
```

저장할 값:

```text
workflow_runs.provider = openai
workflow_runs.request_type = generation_plan
workflow_runs.model = used model
workflow_runs.previous_response_id = previous response id
workflow_runs.response_id = returned response id
workflow_runs.input_json = normalized request
workflow_runs.output_json = structured output
workflow_runs.tool_calls = tool call list
workflow_runs.usage_json = token usage
```

### 14.3 generation job을 Supabase에 저장

생성 요청 시:

```text
chat_threads.status = generating
generation_jobs.status = queued
generation_jobs.input_asset_id = uploaded asset id
generation_jobs.workflow_run_id = workflow run id
generation_jobs.workflow_provider = openai
generation_jobs.model_provider = modal
```

### 14.4 Modal job 실행

Railway에서 Modal에 넘길 값:

```text
job_id
workspace_id
thread_id
workflow_run_id
input_asset_object_key
prompt
brief
generation_plan
model_name
params
output_prefix
```

### 14.5 결과 저장

Modal worker:

```text
1. R2에서 입력 이미지 다운로드
2. 모델 실행
3. 결과 이미지를 R2에 업로드
4. 결과 metadata JSON을 R2에 업로드
5. Railway callback 또는 Supabase update 호출
```

Railway:

```text
1. assets row 생성
2. generation_outputs row 생성
3. generation_jobs.status = succeeded
4. chat_threads.status = completed
5. final_output_id 설정
6. usage_events 기록
```

### 14.6 실패 처리

실패 시:

```text
generation_jobs.status = failed
generation_jobs.error_code = ...
generation_jobs.error_message = ...
generation_job_events에 실패 이벤트 저장
workflow_runs.status = failed, workflow 단계 실패일 경우
chat_threads.status = failed
```

UI는 retry 버튼을 제공하고, retry는 새 `generation_jobs` row를 생성합니다.

## 15. Phase 9, 전체 smoke test

### 15.1 기본 헬스체크

```bash
curl https://<railway-bff-domain>/health
curl https://<railway-orchestrator-domain>/health
```

### 15.2 UI 접속

```text
https://<vercel-domain>
```

확인:

```text
1. 홈 화면 표시
2. 온보딩 표시
3. /generate/chat 접근
4. 대화 입력
5. BFF API 요청 성공
6. orchestrator 로그 확인
```

### 15.3 사진 업로드

R2 연동 전:

```text
운영 배포에서 실제 사진 업로드를 공개하지 않는다.
로컬 또는 internal preview에서만 확인한다.
```

R2 연동 후:

```text
1. 사진 업로드
2. R2 object 생성 확인
3. Supabase assets row 생성 확인
4. workflow_runs row 생성 확인
5. generation_jobs row 생성 확인
6. Modal 실행 확인
7. generation_outputs row 생성 확인
8. UI에서 결과 이미지 표시 확인
```

### 15.4 로그 확인 위치

```text
Vercel
  -> frontend build/runtime logs

Railway BFF
  -> incoming API requests
  -> CORS errors
  -> orchestrator proxy errors

Railway orchestrator
  -> marketing graph errors
  -> OpenAI SDK workflow errors
  -> structured output validation errors
  -> tool/function call errors
  -> validation errors
  -> generation job errors

Supabase
  -> SQL logs
  -> Auth logs
  -> RLS policy issues

Cloudflare R2
  -> object existence
  -> request count

Modal
  -> GPU worker logs
  -> cold start
  -> model load
  -> runtime errors
```

## 16. 운영 전 보안 체크리스트

```text
[ ] .env 파일이 git에 올라가지 않는다.
[ ] Vercel에는 public env만 있다.
[ ] Railway에만 service role keys가 있다.
[ ] OPENAI_API_KEY는 Railway orchestrator에만 있다.
[ ] Supabase RLS가 사용자 데이터 테이블에 켜져 있다.
[ ] R2 secret key가 브라우저에 노출되지 않는다.
[ ] Modal token이 브라우저에 노출되지 않는다.
[ ] CORS_ORIGIN이 production Vercel domain으로 제한되어 있다.
[ ] API cost guard가 켜져 있다.
[ ] 실제 GPU/API 경로는 internal preview에서 먼저 검증한다.
[ ] 실패한 workflow, job, usage event가 DB에 기록된다.
```

## 17. 비용 가드레일

초기 기본값:

```text
T2I_DEFAULT_ENGINE=mock
T2I_ALLOW_API_CALLS=false
T2I_ENABLE_API_COST_GUARD=true
LLM_ENABLE_API_CALL=false
LLM_DEFAULT_PROVIDER=mock
OPENAI_STORE_RESPONSES=true
OPENAI_WORKFLOW_STRICT_SCHEMA=true
```

실제 생성 테스트를 열 때:

```text
1. 내부 계정만 접근 가능하게 한다.
2. workspace별 일일 생성 제한을 둔다.
3. EASYADS_T2I_MAX_IMAGES_PER_JOB=1로 시작한다.
4. Modal concurrency를 낮게 시작한다.
5. OpenAI SDK 호출 횟수와 token usage를 workflow_runs에 기록한다.
6. usage_events에 estimated_cost를 기록한다.
```

권장 제한:

```text
dev workspace: 하루 20 jobs 이하
prod internal beta: 사용자당 하루 5 jobs 이하
한 job당 결과 이미지 1장부터 시작
OpenAI workflow call은 생성 job당 1~3회로 시작
```

## 18. 자주 나는 문제

### 18.1 Vercel에서 API가 localhost로 나감

증상:

```text
Network request가 http://127.0.0.1:4000으로 나간다.
```

해결:

```text
Vercel 환경변수 NEXT_PUBLIC_BFF_BASE_URL 확인
변경 후 redeploy 필요
```

### 18.2 BFF에서 orchestrator 연결 실패

증상:

```text
upstream_error
orchestrator request failed
```

해결:

```text
Railway BFF의 ORCHESTRATOR_BASE_URL 확인
orchestrator /health 확인
Railway private/public domain 확인
```

### 18.3 CORS 에러

증상:

```text
Browser console에 CORS policy error
```

해결:

```text
BFF CORS_ORIGIN에 Vercel production domain 추가
preview domain을 테스트할 경우 preview domain도 추가
```

현재 BFF는 `CORS_ORIGIN`이 없으면 모든 origin을 허용합니다.
운영에서는 production domain으로 제한하는 것이 좋습니다.

### 18.4 Supabase RLS로 데이터가 안 보임

증상:

```text
DB에는 row가 있는데 frontend/API에서 empty로 보인다.
```

확인:

```text
RLS policy
workspace_members row
auth.uid()
service role 사용 여부
```

### 18.5 R2에 파일은 있는데 UI에서 이미지가 안 보임

확인:

```text
object_key 정확성
signed URL 만료
content-type
bucket public/private 설정
CORS 설정
```

### 18.6 Modal cold start가 느림

해결 방향:

```text
모델 cache/Volume 확인
이미지 빌드 단계에서 dependency 설치
필요할 때만 warm pool 설정
초기 MVP에서는 느린 첫 요청을 허용
```

### 18.7 OpenAI workflow structured output 검증 실패

증상:

```text
OpenAI 응답은 왔지만 Pydantic/Zod schema validation에서 실패한다.
```

해결:

```text
workflow_runs.output_json 원본 확인
schema 필드명/required 값 확인
prompt의 output contract 확인
동일 입력으로 재시도 row를 새로 생성
```

### 18.8 previous_response_id가 꼬여 대화 맥락이 이상함

확인:

```text
chat_threads.openai_last_response_id
workflow_runs.previous_response_id
workflow_runs.response_id
같은 thread에서 최신 response id가 올바르게 갱신됐는지 확인
```

해결:

```text
Supabase chat_messages 기록으로 context를 수동 재구성한다.
필요하면 previous_response_id 없이 새 workflow_runs row를 생성한다.
```

## 19. 팀 작업 순서 추천

### Sprint A, 배포 골격

```text
[ ] Vercel UI 배포
[ ] Railway BFF 배포
[ ] Railway orchestrator 배포
[ ] Vercel -> BFF -> orchestrator 연결
[ ] mock chat/generation flow smoke test
```

### Sprint B, DB 도입

```text
[ ] Supabase project 생성
[ ] Auth redirect URL 설정
[ ] DB schema migration 작성
[ ] RLS policy 작성
[ ] Railway에서 Supabase service role 연결
[ ] chat_threads/workflow_runs/generation_jobs 저장 시작
```

### Sprint C, OpenAI SDK workflow 도입

```text
[ ] OpenAI SDK adapter 작성
[ ] Responses API 기반 workflow contract 작성
[ ] structured output schema 작성
[ ] previous_response_id 저장/갱신 구현
[ ] workflow_runs 기록
[ ] tool/function call handler skeleton 작성
```

### Sprint D, R2 도입

```text
[ ] R2 bucket 생성
[ ] R2 access key 생성
[ ] Railway orchestrator에 EASYADS_R2_* 환경변수 등록
[ ] EASYADS_ASSET_STORAGE_BACKEND=r2 설정
[ ] EASYADS_ENABLE_R2_UPLOAD=true 설정
[ ] assets table 기록
[ ] signed URL 발급
[ ] UI 이미지 표시 확인
```

### Sprint E, Modal 도입

```text
[ ] Modal app 생성
[ ] HF_TOKEN, R2 secrets 등록
[ ] mock Modal worker 작성
[ ] OpenAI generation_plan을 Modal input으로 변환
[ ] Railway에서 Modal 호출
[ ] generation_jobs 상태 업데이트
[ ] 실제 GPU 모델 1개만 연결
```

### Sprint F, 운영 안정화

```text
[ ] usage_events 비용 추적
[ ] workflow_runs usage 추적
[ ] job retry 정책
[ ] 실패 화면 개선
[ ] admin/debug 화면
[ ] 로그와 알림
[ ] daily cost cap
```

## 20. 참고 문서

- OpenAI SDKs and CLI: https://developers.openai.com/api/docs/libraries
- OpenAI Conversation state: https://developers.openai.com/api/docs/guides/conversation-state
- OpenAI Function calling: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI Structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- Vercel Pricing: https://vercel.com/pricing
- Railway Pricing Plans: https://docs.railway.com/pricing/plans
- Supabase Pricing: https://supabase.com/pricing
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase DB connections: https://supabase.com/docs/guides/database/connecting-to-postgres
- Cloudflare R2 Pricing: https://developers.cloudflare.com/r2/pricing/
- Modal Pricing: https://modal.com/pricing
- Modal GPU: https://modal.com/docs/guide/gpu
- Modal Volumes: https://modal.com/docs/guide/volumes

## 21. 현재 코드 기준 주의사항

현재 repo 기준으로 바로 가능한 것:

```text
apps/web Next.js production build
apps/bff Fastify BFF deploy
orchestrator FastAPI deploy
mock/fallback 기반 UI 플로우 확인
```

추가 구현이 필요한 것:

```text
Supabase schema/migrations
Supabase Auth 연동
OpenAI SDK workflow adapter
Responses API previous_response_id tracking
structured output schema validation
workflow_runs persistence
R2 upload/download adapter
assets metadata persistence
Modal GPU worker
generation_jobs persistence
generation_outputs persistence
usage_events persistence
signed URL 기반 이미지 표시
```

따라서 첫 배포 목표는 다음처럼 잡습니다.

```text
Goal 1:
Vercel UI에서 Railway BFF와 orchestrator mock flow가 동작한다.

Goal 2:
Supabase에 대화창, 메시지, workflow_runs, generation job 기록이 남는다.

Goal 3:
OpenAI SDK workflow가 structured output으로 generation plan을 만들고, 사진 파일이 R2에 저장된다.

Goal 4:
Modal이 OpenAI generation_plan을 받아 실제 GPU 작업을 실행하고, 결과 이미지를 R2에 저장한다.
```

## 22. CI Docker Tag Policy

The deploy workflow must treat pull requests as build-only validation.

- `pull_request`: run secret scan, orchestrator tests, BFF tests, web tests, web type-check, web lint, and Docker build with `push: false`.
- `push` to `main`: run the same quality gates, then push Docker tags.
- `latest`: only created and pushed for `push` events on `refs/heads/main`.
- `sha-*`: generated by Docker metadata for traceability; pushed only when Docker push is enabled.
- Docker Hub login is skipped unless the event is `push` on `main`, so PRs do not require Docker secrets.
